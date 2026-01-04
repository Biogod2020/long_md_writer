/**
 * SOTA-01: The Geometric Engine - Interactive Core
 * Features: TOC ScrollSpy, Code Utils, Math Rendering, Progress Bar, 
 * Dark Mode, SVG Loss Landscape, Learning Rate Simulation, Backprop Step-through.
 * 
 * Author: JavaScript Expert
 * License: MIT
 */

"use strict";

class GeometricEngine {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupDarkMode();
            this.setupReadingProgress();
            this.setupTOC();
            this.setupCodeBlocks();
            this.initMathJax();
            this.initLossLandscape();
            this.initLearningRateSlider();
            this.initBackpropStepThrough();
        });
    }

    /**
     * 1. Dark Mode Toggle Logic
     * Defaults to "SOTA High-Tech Dark" (#0f172a)
     */
    setupDarkMode() {
        const toggle = document.querySelector('#dark-mode-toggle');
        if (!toggle) return;

        const setTheme = (isDark) => {
            document.documentElement.classList.toggle('light-mode', !isDark);
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        };

        toggle.addEventListener('click', () => {
            const isDark = !document.documentElement.classList.contains('light-mode');
            setTheme(!isDark);
        });

        // Initialize based on preference
        if (localStorage.getItem('theme') === 'light') setTheme(false);
    }

    /**
     * 2. Reading Progress Bar
     */
    setupReadingProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'reading-progress-bar';
        Object.assign(progressBar.style, {
            position: 'fixed',
            top: 0,
            left: 0,
            height: '4px',
            background: 'linear-gradient(to right, #22d3ee, #a855f7)',
            zIndex: 9999,
            width: '0%',
            transition: 'width 0.1s ease-out'
        });
        document.body.appendChild(progressBar);

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + "%";
        });
    }

    /**
     * 3. Table of Contents with Scroll Spy
     */
    setupTOC() {
        const tocContainer = document.querySelector('#toc');
        const headers = Array.from(document.querySelectorAll('h1, h2, h3'));
        if (!tocContainer || headers.length === 0) return;

        const tocList = document.createElement('ul');
        headers.forEach((header, index) => {
            const id = header.id || `header-${index}`;
            header.id = id;

            const li = document.createElement('li');
            li.className = `toc-item toc-${header.tagName.toLowerCase()}`;
            const a = document.createElement('a');
            a.href = `#${id}`;
            a.textContent = header.textContent;
            li.appendChild(a);
            tocList.appendChild(li);
        });
        tocContainer.appendChild(tocList);

        // Scroll Spy using IntersectionObserver
        const observerOptions = { rootMargin: '-100px 0px -70% 0px', threshold: 0 };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    document.querySelectorAll('.toc-item a').forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === `#${entry.target.id}`);
                    });
                }
            });
        }, observerOptions);

        headers.forEach(header => observer.observe(header));
    }

    /**
     * 4. Code Block Utilities (Copy Button)
     */
    setupCodeBlocks() {
        const blocks = document.querySelectorAll('pre');
        blocks.forEach(block => {
            const container = document.createElement('div');
            container.className = 'code-wrapper';
            block.parentNode.insertBefore(container, block);
            container.appendChild(block);

            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.innerHTML = '<span>Copy</span>';
            container.appendChild(copyBtn);

            copyBtn.addEventListener('click', async () => {
                const code = block.querySelector('code').innerText;
                await navigator.clipboard.writeText(code);
                copyBtn.classList.add('copied');
                copyBtn.innerHTML = '<span>Copied!</span>';
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    copyBtn.innerHTML = '<span>Copy</span>';
                }, 2000);
            });
        });
    }

    /**
     * 5. MathJax Initialization
     */
    initMathJax() {
        if (window.MathJax) {
            window.MathJax.typesetPromise();
        }
    }

    /**
     * 6. Custom Element: SVG Loss Landscape
     * Implements click-to-gradient logic
     */
    initLossLandscape() {
        const svg = document.querySelector('#loss-landscape-svg');
        if (!svg) return;

        // Simplified Loss Function: J(x, y) = x^2 + y^2 (Paraboloid)
        // Gradient: ∇J = [2x, 2y]
        svg.addEventListener('click', (e) => {
            const rect = svg.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Center of SVG is (0,0) in our math space
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const dx = (x - centerX) / 20;
            const dy = (y - centerY) / 20;

            // Remove old gradient arrows
            const oldArrow = svg.querySelector('.gradient-arrow');
            if (oldArrow) oldArrow.remove();

            // Create SVG Arrow representing -∇J (Descent direction)
            const arrow = document.createElementNS("http://www.w3.org/2000/svg", "line");
            arrow.setAttribute("x1", x);
            arrow.setAttribute("y1", y);
            arrow.setAttribute("x2", x - dx * 10); // Pointing towards minimum
            arrow.setAttribute("y2", y - dy * 10);
            arrow.setAttribute("stroke", "#f43f5e"); // Rose color for error signal
            arrow.setAttribute("stroke-width", "2");
            arrow.setAttribute("marker-end", "url(#arrowhead)");
            arrow.setAttribute("class", "gradient-arrow");
            
            svg.appendChild(arrow);
            
            // Dispatch event for UI updates
            console.log(`Gradient at (${dx.toFixed(2)}, ${dy.toFixed(2)}): [${(2*dx).toFixed(2)}, ${(2*dy).toFixed(2)}]`);
        });
    }

    /**
     * 7. Custom Element: Learning Rate Slider
     */
    initLearningRateSlider() {
        const slider = document.querySelector('#lr-slider');
        const ball = document.querySelector('#optimizer-ball');
        if (!slider || !ball) return;

        slider.addEventListener('input', (e) => {
            const lr = parseFloat(e.target.value);
            // Update CSS variable or trigger animation speed
            ball.style.animationDuration = `${1 / lr}s`;
            
            const lrDisplay = document.querySelector('#lr-value');
            if (lrDisplay) lrDisplay.textContent = lr.toFixed(4);
            
            // Visual feedback: change color if LR is too high (divergence)
            if (lr > 0.8) {
                ball.style.fill = "#f43f5e"; // Danger
            } else {
                ball.style.fill = "#22d3ee"; // Optimal
            }
        });
    }

    /**
     * 8. Custom Element: Progressive Disclosure (Backprop)
     */
    initBackpropStepThrough() {
        const steps = document.querySelectorAll('.backprop-step');
        const nextBtn = document.querySelector('#next-step-btn');
        let currentStep = 0;

        if (!nextBtn || steps.length === 0) return;

        nextBtn.addEventListener('click', () => {
            if (currentStep < steps.length) {
                const step = steps[currentStep];
                step.classList.add('is-visible');
                step.style.opacity = '1';
                step.style.transform = 'translateY(0)';
                
                // Highlight corresponding math node
                const nodeId = step.getAttribute('data-node-id');
                const node = document.getElementById(nodeId);
                if (node) {
                    node.classList.add('highlight-pulse');
                }

                currentStep++;
                if (currentStep === steps.length) {
                    nextBtn.textContent = "Sequence Complete";
                    nextBtn.disabled = true;
                }
            }
        });
    }
}

// Instantiate the engine
const engine = new GeometricEngine();

/**
 * CSS styles required for the JS logic (can be injected or placed in <style>)
 */
const style = document.createElement('style');
style.textContent = `
    .reading-progress-bar { pointer-events: none; }
    .code-wrapper { position: relative; margin: 1.5em 0; }
    .copy-btn { 
        position: absolute; top: 0.5rem; right: 0.5rem; 
        background: rgba(34, 211, 238, 0.1); border: 1px solid #22d3ee;
        color: #22d3ee; padding: 4px 8px; border-radius: 4px; cursor: pointer;
        font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;
        transition: all 0.2s;
    }
    .copy-btn:hover { background: #22d3ee; color: #0f172a; }
    .toc-item a.active { color: #22d3ee; font-weight: bold; border-left: 2px solid #22d3ee; padding-left: 8px; }
    .backprop-step { opacity: 0; transform: translateY(10px); transition: all 0.5s ease-out; }
    .highlight-pulse { animation: pulse 2s infinite; stroke: #a855f7 !important; stroke-width: 3px !important; }
    @keyframes pulse { 
        0% { filter: drop-shadow(0 0 2px #a855f7); } 
        50% { filter: drop-shadow(0 0 10px #a855f7); } 
        100% { filter: drop-shadow(0 0 2px #a855f7); } 
    }
`;
document.head.appendChild(style);