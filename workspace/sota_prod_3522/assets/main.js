/**
 * Advanced Cardiovascular Electrophysiology - Interactive Engine
 * Features: TOC Scroll Spy, Code Utilities, MathJax Loader, Reading Progress, 
 * Dark Mode, and Cardiac Vector/AP Logic.
 */

class ElectrophysiologyDoc {
    constructor() {
        this.init();
    }

    init() {
        this.setupDarkMode();
        this.setupReadingProgress();
        this.setupTableOfContents();
        this.setupCodeBlocks();
        this.setupMathJax();
        this.initCustomInteractions();
        
        console.log("ECG Technical Doc Engine Initialized.");
    }

    /**
     * 1. Dark Mode Toggle (SOTA High-Tech Dark)
     * Primary Background: #0f172a
     */
    setupDarkMode() {
        const toggle = document.getElementById('dark-mode-toggle');
        const setTheme = (isDark) => {
            document.documentElement.classList.toggle('dark-theme', isDark);
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        };

        if (toggle) {
            toggle.addEventListener('click', () => {
                const isDark = !document.documentElement.classList.contains('dark-theme');
                setTheme(isDark);
            });
        }

        // Initialize based on preference
        const savedTheme = localStorage.getItem('theme') || 'dark';
        setTheme(savedTheme === 'dark');
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
            background: 'var(--accent-cyan, #22d3ee)',
            width: '0%',
            zIndex: 1000,
            transition: 'width 0.1s ease'
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
     * 3. TOC with Scroll Spy
     */
    setupTableOfContents() {
        const tocContainer = document.querySelector('#toc');
        const headings = document.querySelectorAll('h1, h2, h3');
        if (!tocContainer || headings.length === 0) return;

        const tocList = document.createElement('ul');
        
        headings.forEach((heading, index) => {
            const id = heading.id || `heading-${index}`;
            heading.id = id;

            const li = document.createElement('li');
            li.className = `toc-item toc-${heading.tagName.toLowerCase()}`;
            const a = document.createElement('a');
            a.href = `#${id}`;
            a.textContent = heading.textContent;
            li.appendChild(a);
            tocList.appendChild(li);
        });
        tocContainer.appendChild(tocList);

        // Scroll Spy Logic
        const observerOptions = {
            root: null,
            rootMargin: '0px 0px -80% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    document.querySelectorAll('.toc-item a').forEach(link => {
                        link.classList.toggle('active', link.getAttribute('href') === `#${entry.target.id}`);
                    });
                }
            });
        }, observerOptions);

        headings.forEach(h => observer.observe(h));
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
            copyBtn.innerText = 'Copy';
            container.appendChild(copyBtn);

            copyBtn.addEventListener('click', () => {
                const code = block.querySelector('code').innerText;
                navigator.clipboard.writeText(code).then(() => {
                    copyBtn.innerText = 'Copied!';
                    setTimeout(() => copyBtn.innerText = 'Copy', 2000);
                });
            });
        });
    }

    /**
     * 5. Math Rendering (MathJax Configuration)
     */
    setupMathJax() {
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\(', '\\)']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']],
                processEscapes: true
            },
            options: {
                enableMenu: false
            }
        };
        
        // Dynamically load MathJax script
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js';
        script.async = true;
        document.head.appendChild(script);
    }

    /**
     * 6. Custom Interactive Elements Logic
     * Includes Einthoven Triangle Projection and AP Curve manipulation
     */
    initCustomInteractions() {
        this.initEinthovenDashboard();
        this.initAPSlider();
    }

    /**
     * Einthoven's Triangle Lead Projection Logic
     * Projects a 2D cardiac vector onto standard lead axes
     */
    initEinthovenDashboard() {
        const leads = {
            'I': 0,          // 0 degrees
            'II': 60,        // 60 degrees
            'III': 120,      // 120 degrees
            'aVL': -30,
            'aVR': -150,
            'aVF': 90
        };

        // Core Projection Function
        const calculateDeflection = (vectorMag, vectorAngleDeg, leadAngleDeg) => {
            const theta = (vectorAngleDeg - leadAngleDeg) * (Math.PI / 180);
            return vectorMag * Math.cos(theta);
        };

        // Interface Hook (Example usage for an interactive SVG)
        window.updateLeadProjections = (mag, angle) => {
            Object.keys(leads).forEach(leadId => {
                const deflection = calculateDeflection(mag, angle, leads[leadId]);
                const element = document.getElementById(`lead-value-${leadId}`);
                if (element) {
                    element.textContent = deflection.toFixed(2) + ' mV';
                    element.style.color = deflection >= 0 ? '#22d3ee' : '#ef4444';
                }
            });
        };
    }

    /**
     * Action Potential (AP) Slider Logic
     * Manipulates Phase 3 (Repolarization) based on K+ blockade
     */
    initAPSlider() {
        const slider = document.querySelector('#k-blockade-slider');
        const apPath = document.querySelector('#ap-curve-path');

        if (!slider || !apPath) return;

        const updateAPCurve = (kBlockValue) => {
            // kBlockValue from 0 to 1
            const phase3Extension = kBlockValue * 150; // Extend the curve
            
            // SVG Path Data (Simplified Action Potential Shape)
            // M: Start, L: Phase 0, L: Phase 1/2, Q: Phase 3 (Repol), L: Phase 4
            const d = `
                M 0 200 
                L 10 20 
                L 60 30 
                Q ${100 + phase3Extension} 30, ${150 + phase3Extension} 200 
                L ${300 + phase3Extension} 200
            `;
            
            apPath.setAttribute('d', d);
            
            // Trigger a custom event for linked ECG traces to update QT interval
            const event = new CustomEvent('apUpdate', { detail: { qtExtension: phase3Extension } });
            window.dispatchEvent(event);
        };

        slider.addEventListener('input', (e) => {
            updateAPCurve(parseFloat(e.target.value));
        });
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    new ElectrophysiologyDoc();
});