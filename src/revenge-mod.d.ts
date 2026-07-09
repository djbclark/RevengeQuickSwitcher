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
  export const logger: {
    error: (...args: unknown[]) => void;
    info?: (...args: unknown[]) => void;
  };
}

declare module "@revenge-mod/commands" {
  export function registerCommand(command: {
    name: string;
    description?: string;
    /**
     * Revenge shows the command only when `shouldHide?.() !== false`.
     * That means `() => false` hides it; omit this field (or return true) to show.
     */
    shouldHide?: () => boolean;
    applicationId?: string;
    type?: number;
    inputType?: number;
    displayName?: string;
    displayDescription?: string;
    options?: Array<{
      name: string;
      type: number;
      description: string;
      displayName?: string;
      displayDescription?: string;
      required?: boolean;
    }>;
    execute: (args: unknown) => unknown;
  }): () => void;
}

declare module "@revenge-mod/plugin" {
  export const storage: {
    flatSidebar?: boolean;
    aliases?: string;
    debugLogging?: boolean;
    recentIds?: string;
    recentHistorySize?: number;
    excludes?: string;
    hideExcludedFromList?: boolean;
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
