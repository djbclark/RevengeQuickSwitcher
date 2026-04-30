# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client.

## ⚡ Plugin Features
* **Fuzzy-Search Navigation**: Jump instantly to any server via subsequence matching (e.g., typing `wsh` will successfully find `Wayland High School`).
* **Custom Aliases**: Map shortcodes to full server names in settings (e.g., typing `chess` to jump to `Maynard-area Chess Club`).
* **Flat Sidebar Mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list.
* **Smart Pagination**: Automatically chunks outputs into 40-server pages to comply with Discord's strict 2000-character limits, complete with numeric aliases (`/servers 2`).

## 🤖 AI Crowd-Sourcing
This project is built using a continuous human-AI collaboration loop, and we want to see what your AI can do with it!

1. Grab the raw **[Polyglot Source File (PROMPT_FOR_SECOND_OPINION.md)](https://github.com/djbclark/RevengeQuickSwitcher/blob/main/PROMPT_FOR_SECOND_OPINION.md)**.
2. Feed the entire text into your favorite LLM (Gemini, Claude, GPT-4, Grok, etc.).
3. Ask it for an architectural review, a bug hunt, or a new feature implementation.
4. **[Open a GitHub Issue](https://github.com/djbclark/RevengeQuickSwitcher/issues/new)** and paste the AI's suggestions or code output!

## 🛠 Developer Pipeline
This project is powered by a custom "Polyglot" architecture that completely abstracts Git and NPM. Developers can bootstrap, compile (via `esbuild`), and push changes using a single command:
`make push`

## 📦 Installation (Revenge Client)
1. Copy this repository URL: `https://github.com/djbclark/RevengeQuickSwitcher`
2. Open Discord on your device and navigate to **User Settings > Revenge > Plugins**.
3. Tap the **+** icon and paste the URL.
4. Reload the client.
