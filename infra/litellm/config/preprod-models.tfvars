# Shared source for proxy endpoints and the team/key model allowlists.
# Pass this file after the ignored environment and release variable files.
model = "gemini-3.8-flash"
additional_vertex_models = [
  "gemini-3.5-flash",
  "gemini-3.5-flash-lite",
  "gemini-3.6-flash",
  "gemini-3.7-flash",
  "gemini-4-argon",
  "gemini-4-carbon",
  "gemini-4-hydrogen",
  "gemini-4-neon",
]
# Gemini 4 is served only by the Vertex global endpoint, not vertex_location (eu).
global_vertex_models = [
  "gemini-4-argon",
  "gemini-4-carbon",
  "gemini-4-hydrogen",
  "gemini-4-neon",
]
