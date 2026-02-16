# Installation

OSE-MCP is a local MCP server that provides a complete **Old School Essentials solo / GM-less toolkit** for use with Claude Desktop.

---

## Requirements

- macOS, Linux, or Windows (WSL recommended)
- Claude Desktop
- Python **3.10+** (3.11–3.13 recommended)
- Git

---

## 1. Clone the repository

```bash
git clone https://github.com/universalinterchange/ose-mcp.git
cd ose-mcp
```

---

## 2. Create a virtual environment

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

---

## 3. Install OSE-MCP

Install in editable mode:

```bash
pip install -e .
```

This installs the MCP server and all dependencies.

---

## 4. Configure Claude Desktop

Open the Claude Desktop config file:

| OS | Location |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

Add:

```json
{
  "mcpServers": {
    "ose-mcp": {
      "command": "/{PATH TO YOUR INSTALL}/ose-mcp/.venv/bin/ose-mcp"
    }
  }
}
```

---

## 5. Restart Claude Desktop

Fully quit and restart Claude Desktop.

OSE-MCP tools should now be available.

Test with:

```
version()
```

---

## 6. Initialize the campaign database

Run in Claude:

```
init_all()
```

This creates:

```
data/
  campaign.sqlite
  refs.sqlite
```

Verify:

```
doctor()
```

---

## 7. Optional: Load OSE SRD references

If not already loaded:

```
refs_init()
```

Test:

```
search_refs("combat")
```

---

# Quick Start

Create a character:

```
create_pc("Dave", "Fighter")
```

Run the GM loop:

```
gm_step()
```

Search rules:

```
search_refs("turn undead")
```

---

# Updating

Pull latest changes:

```bash
git pull
pip install -e .
```

Restart Claude Desktop.

---

# Running manually (development)

Start server:

```bash
ose-mcp
```

Run diagnostics:

```
doctor()
lint_tools()
```

---

# Data Storage

Campaign data is stored in:

```
data/campaign.sqlite
```

Backup:

```bash
cp data/campaign.sqlite campaign.backup.sqlite
```

---

# Troubleshooting

## MCP server not appearing

Restart Claude Desktop.

Verify config path is correct.

---

## Database issues

Run:

```
doctor()
```

---

## Rebuild reference database

Delete:

```bash
rm data/refs.sqlite
```

Then run:

```
refs_init()
```

---

# Uninstall

```bash
pip uninstall ose-mcp
```
---

# Project Structure

```
ose-mcp/
  src/ose_mcp/
  data/
  .venv/
```

# Quick Install Summary

```bash
git clone https://github.com/universalinterchange/ose-mcp.git
cd ose-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Restart Claude Desktop, then:

```
init_all()
doctor()
help()
create_pc("Test", "Fighter")
gm_step()
```
