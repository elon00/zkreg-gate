FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --prefer-offline --no-audit || true
COPY . .
EXPOSE 3000
CMD ["npm", "start"]