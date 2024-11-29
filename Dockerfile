# Python image 
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev gcc

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to take advantage of Docker caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose the port Flask will run on
EXPOSE 5000

# Set environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Command to run the application
CMD ["flask", "run"]
