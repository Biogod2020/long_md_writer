/**
 * 文档交互功能实现 - 原生 JavaScript 专家版
 * 功能：TOC生成、代码高亮/复制、数学公式、平滑滚动、进度条、暗色模式
 */

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // --- 1. 配置与初始化 ---
    const config = {
        tocSelector: '#toc-container',      // 目录容器
        contentSelector: 'article',         // 正文容器
        prismTheme: 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css',
        mathJaxSrc: 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'
    };

    // --- 2. 辅助函数：动态加载资源 ---
    const loadResource = (type, url) => {
        return new Promise((resolve, reject) => {
            const el = document.createElement(type === 'style' ? 'link' : 'script');
            if (type === 'style') {
                el.rel = 'stylesheet';
                el.href = url;
            } else {
                el.src = url;
                el.async = true;
            }
            el.onload = resolve;
            el.onerror = reject;
            document.head.appendChild(el);
        });
    };

    // --- 3. 阅读进度条 ---
    const initProgressBar = () => {
        const bar = document.createElement('div');
        bar.style = `
            position: fixed; top: 0; left: 0; width: 0%; height: 4px;
            background: #3b82f6; z-index: 9999; transition: width 0.1s ease;
        `;
        document.body.appendChild(bar);

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            bar.style.width = scrolled + "%";
        });
    };

    // --- 4. 自动生成目录 (TOC) 与 滚动高亮 ---
    const initTOC = () => {
        const tocContainer = document.querySelector(config.tocSelector);
        const content = document.querySelector(config.contentSelector);
        if (!tocContainer || !content) return;

        const headers = content.querySelectorAll('h1, h2, h3');
        const tocList = document.createElement('ul');
        tocList.className = 'toc-list';

        const observerOptions = {
            root: null,
            rootMargin: '0px 0px -80% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    document.querySelectorAll('.toc-link').forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
                    });
                }
            });
        }, observerOptions);

        headers.forEach((header, index) => {
            // 确保有 ID 用于跳转
            if (!header.id) {
                header.id = `heading-${index}`;
            }

            const li = document.createElement('li');
            li.className = `toc-item toc-${header.tagName.toLowerCase()}`;
            
            const a = document.createElement('a');
            a.href = `#${header.id}`;
            a.textContent = header.textContent;
            a.className = 'toc-link';
            
            // 平滑滚动点击事件
            a.addEventListener('click', (e) => {
                e.preventDefault();
                header.scrollIntoView({ behavior: 'smooth' });
                history.pushState(null, null, `#${header.id}`);
            });

            li.appendChild(a);
            tocList.appendChild(li);
            observer.observe(header);
        });

        tocContainer.appendChild(tocList);
    };

    // --- 5. 代码块增强：语法高亮与复制 ---
    const initCodeBlocks = async () => {
        // 加载 Prism.js
        await loadResource('style', config.prismTheme);
        await loadResource('script', 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js');
        await loadResource('script', 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-javascript.min.js');

        const blocks = document.querySelectorAll('pre');
        blocks.forEach(block => {
            // 创建复制按钮
            const copyBtn = document.createElement('button');
            copyBtn.innerText = 'Copy';
            copyBtn.className = 'copy-code-btn';
            copyBtn.style = 'position:absolute;right:10px;top:10px;opacity:0.6;cursor:pointer;';
            
            block.style.position = 'relative';
            block.appendChild(copyBtn);

            copyBtn.addEventListener('click', () => {
                const code = block.querySelector('code').innerText;
                navigator.clipboard.writeText(code).then(() => {
                    copyBtn.innerText = 'Copied!';
                    setTimeout(() => copyBtn.innerText = 'Copy', 2000);
                });
            });
        });
        
        if (window.Prism) Prism.highlightAll();
    };

    // --- 6. 数学公式渲染 (MathJax) ---
    const initMathJax = () => {
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\(', '\\)']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']],
                processEscapes: true
            },
            options: {
                ignoreHtmlClass: 'tex2jax_ignore',
                processHtmlClass: 'tex2jax_process'
            }
        };
        loadResource('script', config.mathJaxSrc);
    };

    // --- 7. 暗色模式切换 ---
    const initDarkMode = () => {
        const toggleBtn = document.createElement('button');
        toggleBtn.id = 'theme-toggle';
        toggleBtn.innerHTML = '🌙';
        toggleBtn.style = 'position:fixed; bottom:20px; right:20px; z-index:1000; padding:10px; border-radius:50%; cursor:pointer;';
        document.body.appendChild(toggleBtn);

        const setTheme = (isDark) => {
            document.documentElement.classList.toggle('dark-mode', isDark);
            toggleBtn.innerHTML = isDark ? '☀️' : '🌙';
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        };

        // 初始化检查
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));

        toggleBtn.addEventListener('click', () => {
            const isNowDark = !document.documentElement.classList.contains('dark-mode');
            setTheme(isNowDark);
        });
    };

    // --- 8. 执行初始化 ---
    const init = () => {
        initProgressBar();
        initTOC();
        initCodeBlocks();
        initMathJax();
        initDarkMode();
        
        // 全局平滑滚动 CSS 补丁
        const style = document.createElement('style');
        style.textContent = `
            html { scroll-behavior: smooth; }
            .dark-mode { background: #1a1a1a; color: #e5e7eb; }
            .dark-mode pre { filter: brightness(0.9); }
            .toc-link.active { color: #3b82f6; font-weight: bold; border-left: 2px solid #3b82f6; padding-left: 5px; }
            .toc-list { list-style: none; padding-left: 10px; }
            .toc-h2 { margin-left: 15px; font-size: 0.9em; }
            .toc-h3 { margin-left: 30px; font-size: 0.8em; }
            .copy-code-btn:hover { opacity: 1 !important; }
        `;
        document.head.appendChild(style);
    };

    init();
});