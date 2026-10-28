import {defineConfig} from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({plugins:[tailwindcss()],esbuild:{jsx:'automatic'},server:{proxy:{'/api':'http://127.0.0.1:8765'}},test:{exclude:['node_modules/**','dist/**']}});
