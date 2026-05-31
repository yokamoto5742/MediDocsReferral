from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3.5-flash",
    input="AIの仕組みを短い言葉で説明してください"
)

print(interaction.output_text)
