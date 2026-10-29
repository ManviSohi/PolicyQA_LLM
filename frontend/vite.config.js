import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(function (_a) {
    var _b;
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), '');
    var target = ((_b = env.VITE_API_PROXY_TARGET) === null || _b === void 0 ? void 0 : _b.trim()) || 'http://127.0.0.1:8000';
    return {
        plugins: [react()],
        server: {
            proxy: {
                '/api': {
                    target: target,
                    changeOrigin: true,
                },
            },
        },
    };
});
