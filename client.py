from mcp.client import MCPServerStreamableHttp

client = MCPServerStreamableHttp("http://127.0.0.1:8000")
print(client.add(a=5, b=9))  # Should print 14
