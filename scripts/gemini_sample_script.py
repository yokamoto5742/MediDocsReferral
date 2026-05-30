from google import genai
from google.genai import types

client = genai.Client(
  vertexai=True, project="gen-lang-client-0605794434", location="global",
)

IMAGE_URI = "gs://generativeai-downloads/images/scones.jpg"
model = "gemini-3.5-flash"
response = client.models.generate_content(
  model=model,
  contents=[
    "この画像には何が写っていますか?",
    types.Part.from_uri(
      file_uri=IMAGE_URI,
      mime_type="image/png",
    ),
  ],
)
print(response.text, end="")
