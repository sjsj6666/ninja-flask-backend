import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        account: resolve(__dirname, 'account.html'),
        auth: resolve(__dirname, 'auth.html'),
        blog: resolve(__dirname, 'blog.html'),
        games: resolve(__dirname, 'games.html'),
        invite: resolve(__dirname, 'invite.html'),
        login: resolve(__dirname, 'login.html'),
        orderDetails: resolve(__dirname, 'order-details.html'),
        paymentGateway: resolve(__dirname, 'payment-gateway.html'),
        paymentPage: resolve(__dirname, 'payment-page.html'),
        post: resolve(__dirname, 'post.html'),
        topup: resolve(__dirname, 'topup-page.html'),
        // Admin folder files
        admin: resolve(__dirname, 'admin/index.html'),
        adminLogin: resolve(__dirname, 'admin/login.html')
      },
    },
  },
});
