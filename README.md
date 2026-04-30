# RevengeQuickSwitcher

A high-performance server navigation utility built natively for the **Revenge** Discord mobile client.

## ⚡ Plugin Features
* **Fuzzy-Search Navigation**: Jump instantly to any server via subsequence matching (e.g., typing `wsh` will successfully find `Wayland High School`).
* **Flat Sidebar Mode**: Overrides Discord's native UI to present an alphabetically sorted, folder-free guild list.
* **Smart Pagination**: Automatically chunks outputs into 40-server pages to comply with Discord's strict 2000-character limits, complete with numeric aliases (`/servers 2`).

## 🛠 Developer Pipeline
This project is powered by a custom "Polyglot" architecture that completely abstracts Git and NPM. Developers can bootstrap, compile (via `esbuild`), and push changes using a single command:
`make push`

## 📦 Installation (Revenge Client)
1. Copy this repository URL: `https://github.com/djbclark/RevengeQuickSwitcher`
2. Open Discord on your device and navigate to **User Settings > Revenge > Plugins**.
3. Tap the **+** icon and paste the URL.
4. Reload the client.

*Built by Danny Clark, Gemini, and Grok.*
