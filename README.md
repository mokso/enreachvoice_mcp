# EnreachVoice API MCP Server
MCP Server proto to connect [EnreachVoice API](https://doc.enreachvoice.com/beneapi/#introduction) to AI.

## Configuraition 

EnereachVoice API credentials are provided as env-variables:

```
ENREACHVOICE_APIUSER=username
ENREACHVOICE_APISECRET=secretkey
```

## Adding to Claude desktop

Add following to `claude_desktop_config.json`

```
{
  "mcpServers": {
    "EnreachVoice": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "mcp[cli]",
        "--env-file",
        "D:\\path\\to\\enreachvoice_mcp\\.env",
        "D:\\path\\to\\enreachvoice_mcp\\main.py"
      ]
    }
  }
}