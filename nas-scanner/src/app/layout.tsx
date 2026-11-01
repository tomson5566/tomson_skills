import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NAS 勒索软件威胁扫描器',
  description:
    '基于 IOC 特征、熵值分析与行为异常检测的 NAS 勒索软件威胁扫描工具，支持群晖 DSM 版本漏洞自检与 NAS 端定时巡检脚本生成。',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`antialiased`}>
        {children}
      </body>
    </html>
  );
}
