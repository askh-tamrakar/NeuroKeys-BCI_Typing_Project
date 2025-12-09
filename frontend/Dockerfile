# Use Node.js LTS (Alpine for smaller size)
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Copy package files first
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the frontend code
COPY . .

# Expose the Vite development port
EXPOSE 5173

# Command to run the dev server
# Note: --host is needed to expose the server outside the container
CMD ["npm", "run", "dev", "--", "--host"]
