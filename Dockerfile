# Use an official Python image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy dependency list and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Run the bot
CMD ["python", "main.py"]