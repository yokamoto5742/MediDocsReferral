from google import genai
from google.genai import types

# 個人のAPIで成功
client = genai.Client(
  vertexai=True, project="gen-lang-client-0183730413", location="global",
)

IMAGE_URI = "gs://generativeai-downloads/images/scones.jpg"
model = "gemini-3.5-flash"
response = client.models.generate_content(
  model=model,
  contents=[
    "What is shown in this image?",
    types.Part.from_uri(
      file_uri=IMAGE_URI,
      mime_type="image/png",
    ),
  ],
)
print(response.text, end="")
