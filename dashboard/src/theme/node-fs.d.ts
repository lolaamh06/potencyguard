// Minimal typing for the one Node call the token test makes (no @types/node is installed).
declare module "node:fs" {
  export function readFileSync(path: URL, encoding: string): string;
}
