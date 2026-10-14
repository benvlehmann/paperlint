import * as vscode from "vscode";
import { spawn } from "child_process";
import * as path from "path";

const LINE = /^(.*):(\d+):(\d+):\s+(error|warning):\s+(.*)\s+\[([A-Za-z0-9_-]+)\]\s*$/;
const TEX_ROOT = /^\s*%\s*!TEX\s+root\s*=\s*(.+?)\s*$/i;

interface PaperlintSettings {
  command: string;
  args: string[];
  root: string;
  run: "onSave" | "onType";
}

let generation = 0;
let reported = new Set<string>();
let missingCommandReported = false;

export function activate(context: vscode.ExtensionContext): void {
  const diagnostics = vscode.languages.createDiagnosticCollection("paperlint");
  const typeTimers = new Map<string, ReturnType<typeof setTimeout>>();

  const lint = (document: vscode.TextDocument | undefined) => {
    if (!document || !isTex(document)) {
      return;
    }
    void run(document, diagnostics);
  };

  context.subscriptions.push(
    diagnostics,
    vscode.workspace.onDidSaveTextDocument((document) => {
      if (isTex(document)) {
        lint(document);
      }
    }),
    vscode.workspace.onDidOpenTextDocument((document) => {
      lint(document);
    }),
    vscode.workspace.onDidChangeTextDocument((event) => {
      if (settings().run !== "onType" || !isTex(event.document)) {
        return;
      }
      const key = event.document.uri.toString();
      const pending = typeTimers.get(key);
      if (pending) {
        clearTimeout(pending);
      }
      typeTimers.set(
        key,
        setTimeout(() => {
          typeTimers.delete(key);
          lint(event.document);
        }, 400),
      );
    }),
    vscode.commands.registerCommand("paperlint.lint", () => {
      lint(vscode.window.activeTextEditor?.document);
    }),
  );

  for (const document of vscode.workspace.textDocuments) {
    lint(document);
  }
}

export function deactivate(): void {}

function isTex(document: vscode.TextDocument): boolean {
  if (document.uri.scheme !== "file") {
    return false;
  }
  return (
    document.languageId === "latex" ||
    document.languageId === "tex" ||
    document.fileName.toLowerCase().endsWith(".tex")
  );
}

function settings(): PaperlintSettings {
  const config = vscode.workspace.getConfiguration("paperlint");
  const run = config.get<string>("run");
  return {
    command: config.get<string>("path") || "paperlint",
    args: config.get<string[]>("args") ?? [],
    root: config.get<string>("root") ?? "",
    run: run === "onType" ? "onType" : "onSave",
  };
}

function resolveTarget(document: vscode.TextDocument): string {
  const configured = settings().root.trim();
  if (configured) {
    if (path.isAbsolute(configured)) {
      return configured;
    }
    const folder = vscode.workspace.getWorkspaceFolder(document.uri)?.uri.fsPath
      ?? vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (folder) {
      return path.resolve(folder, configured);
    }
    return path.resolve(path.dirname(document.uri.fsPath), configured);
  }
  const magic = texRoot(document);
  if (magic) {
    const cleaned = magic.replace(/^["']|["']$/g, "");
    return path.resolve(path.dirname(document.uri.fsPath), cleaned);
  }
  return document.uri.fsPath;
}

function texRoot(document: vscode.TextDocument): string | undefined {
  const limit = Math.min(document.lineCount, 50);
  for (let index = 0; index < limit; index += 1) {
    const match = TEX_ROOT.exec(document.lineAt(index).text);
    if (match) {
      return match[1];
    }
  }
  return undefined;
}

async function run(
  document: vscode.TextDocument,
  diagnostics: vscode.DiagnosticCollection,
): Promise<void> {
  const current = ++generation;
  const target = resolveTarget(document);
  const config = settings();
  let output: { stdout: string; stderr: string; code: number | null; error?: NodeJS.ErrnoException };
  try {
    output = await execute(config.command, [...config.args, target], path.dirname(target));
  } catch (error) {
    const errno = error as NodeJS.ErrnoException;
    if (errno.code === "ENOENT" && !missingCommandReported) {
      missingCommandReported = true;
      void vscode.window.showErrorMessage(
        `paperlint: command not found (${config.command}). Install the package or set paperlint.path.`,
      );
    }
    return;
  }
  if (current !== generation) {
    return;
  }
  if (output.code === 2) {
    const detail = output.stderr.trim() || "paperlint failed";
    void vscode.window.showErrorMessage(detail);
    return;
  }
  apply(diagnostics, output.stdout, path.dirname(target));
}

function execute(
  command: string,
  args: string[],
  cwd: string,
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env: process.env });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk: string) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({ stdout, stderr, code });
    });
  });
}

function apply(
  diagnostics: vscode.DiagnosticCollection,
  stdout: string,
  cwd: string,
): void {
  const grouped = new Map<string, vscode.Diagnostic[]>();
  for (const line of stdout.split(/\r?\n/)) {
    const parsed = parseLine(line, cwd);
    if (!parsed) {
      continue;
    }
    const key = parsed.uri.toString();
    const list = grouped.get(key) ?? [];
    list.push(parsed.diagnostic);
    grouped.set(key, list);
  }
  const next = new Set<string>();
  for (const [key, list] of grouped) {
    diagnostics.set(vscode.Uri.parse(key), list);
    next.add(key);
  }
  for (const key of reported) {
    if (!next.has(key)) {
      diagnostics.delete(vscode.Uri.parse(key));
    }
  }
  reported = next;
}

function parseLine(
  line: string,
  cwd: string,
): { uri: vscode.Uri; diagnostic: vscode.Diagnostic } | undefined {
  const match = LINE.exec(line.trim());
  if (!match) {
    return undefined;
  }
  const [, file, lineText, columnText, severity, message, ruleId] = match;
  const lineNumber = Number(lineText);
  const column = Number(columnText);
  if (!Number.isFinite(lineNumber) || !Number.isFinite(column) || lineNumber < 1) {
    return undefined;
  }
  const absolute = path.isAbsolute(file) ? file : path.resolve(cwd, file);
  const startColumn = Math.max(0, column - 1);
  const range = new vscode.Range(lineNumber - 1, startColumn, lineNumber - 1, startColumn + 1);
  const diagnostic = new vscode.Diagnostic(
    range,
    message,
    severity === "error" ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning,
  );
  diagnostic.source = "paperlint";
  diagnostic.code = ruleId;
  return { uri: vscode.Uri.file(absolute), diagnostic };
}
