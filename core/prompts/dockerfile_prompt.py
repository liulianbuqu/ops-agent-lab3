"""
Dockerfile 生成专用提示词模板
当智能体需要为项目生成 Dockerfile 时使用
"""

DOCKERFILE_PROMPT_TEMPLATE = """
Generate a complete, production-ready Dockerfile for a project based on the following requirements.

## Requirements
{requirement}

## Project Path
{project_path}

## Guidelines
- Choose the appropriate base image based on the project language (node, python, go, java, etc.)
- Use multi-stage builds when appropriate to keep the image size small
- Only use the simplest method mentioned in the requirements to run the app
- Set proper working directory (WORKDIR)
- Copy package manager files first to leverage Docker layer caching
- Install dependencies, then copy source code
- Expose the correct port
- Define the correct CMD or ENTRYPOINT
- Add HEALTHCHECK if appropriate
- Follow Docker best practices (use .dockerignore, avoid running as root, etc.)

## Output Format
Output ONLY the Dockerfile content wrapped in ```dockerfile blocks, no explanation or extra text.

Example:
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
```
"""
