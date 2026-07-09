declare module "@revenge-mod/metro" {
  export function findByProps(...props: string[]): unknown;
}

declare module "@revenge-mod/patcher" {
  export function after(
    name: string,
    target: object,
    callback: (...args: unknown[]) => unknown
  ): () => void;
}

declare module "@revenge-mod/ui/toast" {
  export function showToast(message: string, type?: string): void;
}

declare module "@revenge-mod" {
  export const logger: { error: (...args: unknown[]) => void };
}

declare module "@revenge-mod/commands" {
  export function registerCommand(command: {
    name: string;
    options?: Array<{ name: string; type: number; description: string }>;
    execute: (args: unknown) => unknown;
  }): () => void;
}

declare module "@revenge-mod/plugin" {
  export const storage: {
    flatSidebar?: boolean;
    aliases?: string;
  };
}

declare module "@revenge-mod/storage" {
  export function useProxy<T extends object>(target: T): void;
}

declare module "@revenge-mod/ui/components" {
  export const Forms: {
    FormSwitchRow: import("react").ComponentType<{
      label: string;
      value: boolean;
      onValueChange: (value: boolean) => void;
    }>;
  };
}
