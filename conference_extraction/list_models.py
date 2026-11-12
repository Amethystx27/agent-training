from openai import OpenAI

client = OpenAI(
    base_url="http://43.142.146.132:8000/v1",
    api_key="sk-WXfVsTPZBHxS04ti328942F45f78461c9bA7F1295bE73a34",
)
for m in client.models.list().data:
    print(m.id)