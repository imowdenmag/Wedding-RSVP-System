# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Flask runs on
EXPOSE 8080

# Set environment variables for Flask
ENV PORT=8080
ENV PYTHONUNBUFFERED=True

# Command to run the application
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
