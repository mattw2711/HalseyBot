# HalseyBot - Azure Container App

This project is a Python bot that monitors a website for product changes and posts updates to Twitter. It runs continuously on Azure Container Apps using a Dockerized container.

---

## 🚀 Project Structure

```
HalseyBot/
├── main.py               # The main async bot logic
├── requirements.txt      # Python dependencies
├── Dockerfile            # Defines the container image
├── .env (local)          # Environment variables (not committed)
└── README.md             # You're reading it!
```

---

## 🔁 Redeploying After Code Changes

The deploy.sh script can be ran to build, tag, push and deploy code changes

```bash
./deploy.sh
```

Note: If the file is not executable you must run the following first:

```bash
chmod +x deploy.sh
```

---

## 🔁 Redeploying After Code Changes (Manually)

Whenever you make changes to the bot’s code and want to redeploy it to Azure, follow these steps:

### ✅ 1. Rebuild the Docker image (targeting `linux/amd64`)
```bash
docker build --platform linux/amd64 -t halseybot .
```

### ✅ 2. Tag the image for Azure Container Registry
```bash
docker tag halseybot halseybotacr.azurecr.io/halseybot:latest
```

### ✅ 3. Push the image to Azure Container Registry
```bash
az acr login --name halseybotacr
docker push halseybotacr.azurecr.io/halseybot:latest
```

### ✅ 4. Update the Azure Container App
```bash
az containerapp update \
  --name halseybot \
  --resource-group halseybot-rg \
  --image halseybotacr.azurecr.io/halseybot:latest
```

---

## 🔐 Environment Variables

Environment variables like the Azure Blob Storage connection string should be passed securely.

### Set environment variable in Azure:
```bash
az containerapp update \
  --name halseybot \
  --resource-group halseybot-rg \
  --set-env-vars AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
```

In code (`main.py`):
```python
import os
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
```

---

## 📦 Dependency Management

To add new Python packages:

1. Install locally:
```bash
pip install somepackage
```

2. Freeze the updated list:
```bash
pip freeze > requirements.txt
```

3. Rebuild and redeploy the container as described above.

---

## 🧪 Running Locally

You can also test the bot locally with:

```bash
python main.py
```

To use your `.env` file:
```bash
pip install python-dotenv
```

Then load it in `main.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 📖 Logs & Monitoring

View container logs in real-time:

```bash
az containerapp logs show \
  --name halseybot \
  --resource-group halseybot-rg \
  --follow
```

---

## ✅ Notes

- Make sure your Docker image is always built for `linux/amd64` (Azure requirement).
- Avoid hardcoding secrets — use environment variables or managed identities.
- Azure Container Apps will keep your bot running continuously unless the app crashes or is updated.
