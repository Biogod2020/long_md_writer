/**
 * Medical Interactive Document Engine (MIDE)
 * 核心功能：TOC、代码高亮、公式渲染、阅读进度、暗色模式、医学交互组件
 */

"use strict";

class MedicalDocEngine {
  constructor() {
    this.tocContainer = document.querySelector("#toc-container");
    this.contentArea = document.querySelector("#main-content");
    this.progressBar = document.querySelector("#reading-progress");
    this.headers = [];
    
    // 初始化配置
    this.config = {
      prismCDN: "https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/",
      katexCDN: "https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/"
    };
  }

  init() {
    this.initDarkMode();
    this.initTOC();
    this.initPrism();
    this.initMathJax();
    this.initProgressBar();
    this.initSmoothScroll();
    this.initMedicalInteractions(); // 核心：医学交互逻辑
    
    console.log("🚀 Medical Document Engine Initialized");
  }

  /**
   * 1. 自动生成目录 (TOC) 与 滚动高亮
   */
  initTOC() {
    if (!this.tocContainer || !this.contentArea) return;

    const headerEls = this.contentArea.querySelectorAll("h1, h2, h3");
    const tocList = document.createElement("ul");
    tocList.className = "toc-list";

    headerEls.forEach((header, index) => {
      // 确保 header 有 ID
      if (!header.id) {
        header.id = `heading-${index}`;
      }

      const li = document.createElement("li");
      li.className = `toc-item toc-${header.tagName.toLowerCase()}`;
      
      const link = document.createElement("a");
      link.href = `#${header.id}`;
      link.textContent = header.textContent;
      
      li.appendChild(link);
      tocList.appendChild(li);
      this.headers.push(header);
    });

    this.tocContainer.appendChild(tocList);

    // 滚动高亮监听
    const observerOptions = {
      root: null,
      rootMargin: "0px 0px -80% 0px",
      threshold: 0
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute("id");
          this.updateTOCActiveState(id);
        }
      });
    }, observerOptions);

    this.headers.forEach((h) => observer.observe(h));
  }

  updateTOCActiveState(id) {
    const links = this.tocContainer.querySelectorAll("a");
    links.forEach((link) => {
      link.classList.toggle("active", link.getAttribute("href") === `#${id}`);
    });
  }

  /**
   * 2. 代码块处理：复制按钮与 Prism 高亮
   */
  initPrism() {
    // 动态加载 Prism 样式
    this.loadResource(`${this.config.prismCDN}themes/prism-tomorrow.min.css`, "css");
    
    const codeBlocks = document.querySelectorAll("pre code");
    codeBlocks.forEach((block) => {
      // 添加复制按钮
      const pre = block.parentElement;
      pre.style.position = "relative";
      
      const copyBtn = document.createElement("button");
      copyBtn.className = "copy-code-btn";
      copyBtn.innerHTML = "<span>Copy</span>";
      
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(block.textContent).then(() => {
          copyBtn.textContent = "Copied!";
          setTimeout(() => (copyBtn.textContent = "Copy"), 2000);
        });
      });
      
      pre.appendChild(copyBtn);
    });
  }

  /**
   * 3. 数学公式渲染 (KaTeX)
   */
  initMathJax() {
    this.loadResource(`${this.config.katexCDN}katex.min.css`, "css");
    this.loadResource(`${this.config.katexCDN}katex.min.js`, "js", () => {
      this.loadResource(`${this.config.katexCDN}contrib/auto-render.min.js`, "js", () => {
        renderMathInElement(document.body, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false }
          ]
        });
      });
    });
  }

  /**
   * 4. 阅读进度条
   */
  initProgressBar() {
    if (!this.progressBar) return;
    window.addEventListener("scroll", () => {
      const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
      const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrolled = (winScroll / height) * 100;
      this.progressBar.style.width = scrolled + "%";
    });
  }

  /**
   * 5. 暗色模式切换
   */
  initDarkMode() {
    const toggleBtn = document.querySelector("#dark-mode-toggle");
    const setMode = (isDark) => {
      document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
      localStorage.setItem("theme", isDark ? "dark" : "light");
    };

    // 初始状态
    const savedTheme = localStorage.getItem("theme") || "dark"; // 默认深色
    setMode(savedTheme === "dark");

    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const isDark = document.documentElement.getAttribute("data-theme") === "dark";
        setMode(!isDark);
      });
    }
  }

  /**
   * 6. 平滑滚动
   */
  initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
      anchor.addEventListener("click", function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute("href"));
        if (target) {
          target.scrollIntoView({
            behavior: "smooth",
            block: "start"
          });
        }
      });
    });
  }

  /**
   * 7. 医学交互组件：心脏向量与 PV Loop 模拟
   * 针对文档中提到的“参数滑动条”和“SVG动画”
   */
  initMedicalInteractions() {
    // 示例：心脏电向量旋转逻辑
    const vectorSlider = document.querySelector("#vector-angle-slider");
    const heartVector = document.querySelector("#heart-vector-arrow"); // SVG 元素

    if (vectorSlider && heartVector) {
      vectorSlider.addEventListener("input", (e) => {
        const angle = e.target.value;
        heartVector.style.transform = `rotate(${angle}deg)`;
        // 联动更新 UI 上的数值显示
        const display = document.querySelector("#angle-display");
        if (display) display.textContent = `${angle}°`;
      });
    }

    // 示例：PV Loop 变形逻辑 (基于外周阻力 TPR)
    const tprSlider = document.querySelector("#tpr-slider");
    const pvLoopPath = document.querySelector("#pv-loop-path");

    if (tprSlider && pvLoopPath) {
      tprSlider.addEventListener("input", (e) => {
        const tpr = parseFloat(e.target.value);
        // 模拟 PV Loop 拓扑变形：收缩期压力升高，环向左上方拉伸
        const newWidth = 100 - tpr * 10;
        const newHeight = 100 + tpr * 20;
        pvLoopPath.style.transform = `scale(${newWidth/100}, ${newHeight/100})`;
      });
    }
  }

  /**
   * 辅助工具：动态加载资源
   */
  loadResource(url, type, callback) {
    let el;
    if (type === "css") {
      el = document.createElement("link");
      el.rel = "stylesheet";
      el.href = url;
    } else {
      el = document.createElement("script");
      el.src = url;
      el.async = true;
      if (callback) el.onload = callback;
    }
    document.head.appendChild(el);
  }
}

// DOM 加载完成后启动
document.addEventListener("DOMContentLoaded", () => {
  const engine = new MedicalDocEngine();
  engine.init();
});