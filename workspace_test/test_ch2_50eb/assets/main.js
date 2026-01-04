/**
 * SOTA Technical Specification - Chapter 2 Interactive Engine
 * Features: TOC Scroll-Spy, Code Utilities, MathJax Integration, 
 * Reading Progress, Dark Mode, and ECG Vector Physics Simulations.
 */

class TechnicalDocEngine {
    constructor() {
        this.initTheme();
        this.initNavigation();
        this.initCodeBlocks();
        this.initMathSupport();
        this.initInteractiveComponents();
        this.initProgressTracking();
    }

    // 1. Dark Mode Toggle Logic
    initTheme() {
        const themeToggle = document.querySelector('#theme-toggle');
        const savedTheme = localStorage.getItem('theme') || 'dark';
        
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                const current = document.documentElement.getAttribute('data-theme');
                const next = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem('theme', next);
            });
        }
    }

    // 2. TOC with Scroll Spy
    initNavigation() {
        const tocContainer = document.querySelector('#toc-content');
        const headings = Array.from(document.querySelectorAll('h1, h2, h3'));
        
        if (!tocContainer || headings.length === 0) return;

        // Generate TOC items
        headings.forEach((heading, index) => {
            const id = heading.id || `heading-${index}`;
            heading.id = id;
            
            const link = document.createElement('a');
            link.href = `#${id}`;
            link.textContent = heading.textContent;
            link.className = `toc-link level-${heading.tagName.toLowerCase()}`;
            tocContainer.appendChild(link);
        });

        // Scroll Spy Logic
        const observerOptions = {
            rootMargin: '-10% 0px -80% 0px',
            threshold: 0
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    document.querySelectorAll('.toc-link').forEach(el => el.classList.remove('active'));
                    const activeLink = document.querySelector(`.toc-link[href="#${entry.target.id}"]`);
                    if (activeLink) activeLink.classList.add('active');
                }
            });
        }, observerOptions);

        headings.forEach(h => observer.observe(h));
    }

    // 3. Code Block Utilities (Copy Button)
    initCodeBlocks() {
        document.querySelectorAll('pre').forEach((codeBlock) => {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-code-btn';
            copyBtn.innerHTML = '<span>Copy</span>';
            
            copyBtn.addEventListener('click', async () => {
                const code = codeBlock.querySelector('code').innerText;
                try {
                    await navigator.clipboard.writeText(code);
                    copyBtn.innerText = 'Copied!';
                    setTimeout(() => copyBtn.innerText = 'Copy', 2000);
                } catch (err) {
                    console.error('Failed to copy!', err);
                }
            });

            codeBlock.style.position = 'relative';
            codeBlock.appendChild(copyBtn);
        });
    }

    // 4. MathJax Support
    initMathSupport() {
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\(', '\\)']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']],
                processEscapes: true
            },
            options: {
                enableMenu: false
            },
            startup: {
                pageReady: () => {
                    return MathJax.startup.defaultPageReady().then(() => {
                        console.log('MathJax initial typesetting complete');
                    });
                }
            }
        };

        // Inject MathJax Script if not present
        if (!document.getElementById('mathjax-script')) {
            const script = document.createElement('script');
            script.id = 'mathjax-script';
            script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js';
            script.async = true;
            document.head.appendChild(script);
        }
    }

    // 5. Reading Progress Bar
    initProgressTracking() {
        const progressBar = document.querySelector('#reading-progress');
        if (!progressBar) return;

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + "%";
        });
    }

    // 6. Custom Interactive Elements (ECG Specific)
    initInteractiveComponents() {
        this.initVectorProjection();
        this.initAxisTool();
        this.initProgressiveDisclosure();
    }

    /**
     * Vector Projection Demo Logic
     * Simulates V = |P| * cos(theta)
     */
    initVectorProjection() {
        const heartVector = document.querySelector('#heart-vector');
        const projectionValue = document.querySelector('#projection-math-value');
        
        if (!heartVector) return;

        // Example: Update vector rotation based on a slider or time
        const updateProjection = (angleDegrees) => {
            const rad = (angleDegrees * Math.PI) / 180;
            const length = 120; // Base vector length
            
            // Calculate vector endpoint
            const x2 = 200 + length * Math.cos(rad);
            const y2 = 200 + length * Math.sin(rad);
            
            heartVector.setAttribute('x2', x2);
            heartVector.setAttribute('y2', y2);

            // Update Math Text (Dot Product logic)
            if (projectionValue) {
                const leadAngle = -30; // Lead II is roughly +60 or -30 in this SVG coordinate
                const relativeAngle = angleDegrees - leadAngle;
                const projection = Math.cos((relativeAngle * Math.PI) / 180).toFixed(2);
                projectionValue.textContent = `V ≈ |P| · ${projection}`;
            }
        };

        // Hook into a slider if it exists
        const slider = document.querySelector('#vector-slider');
        if (slider) {
            slider.addEventListener('input', (e) => updateProjection(e.target.value));
        }
    }

    /**
     * The Hexaxial Axis Tool
     * Maps degrees to clinical axis status
     */
    initAxisTool() {
        const axisInput = document.querySelector('#axis-degree-input');
        const axisStatus = document.querySelector('#axis-clinical-status');

        if (!axisInput) return;

        axisInput.addEventListener('input', (e) => {
            const deg = parseInt(e.target.value);
            let status = "";
            let color = "";

            if (deg >= -30 && deg <= 90) {
                status = "Normal Axis (正常心电轴)";
                color = "#10b981"; // Emerald
            } else if (deg < -30 && deg >= -90) {
                status = "Left Axis Deviation (LAD - 左偏)";
                color = "#e11d48"; // Red
            } else if (deg > 90 && deg <= 180) {
                status = "Right Axis Deviation (RAD - 右偏)";
                color = "#f59e0b"; // Amber
            } else {
                status = "Extreme Axis (极度右偏)";
                color = "#7c3aed"; // Purple
            }

            if (axisStatus) {
                axisStatus.textContent = status;
                axisStatus.style.color = color;
            }
            
            // Dispatch custom event for SVG listeners
            window.dispatchEvent(new CustomEvent('axisUpdate', { detail: { degree: deg } }));
        });
    }

    /**
     * Progressive Disclosure (Click-to-Reveal)
     */
    initProgressiveDisclosure() {
        document.querySelectorAll('.disclosure-trigger').forEach(trigger => {
            trigger.addEventListener('click', () => {
                const targetId = trigger.getAttribute('data-target');
                const targetEl = document.getElementById(targetId);
                if (targetEl) {
                    const isHidden = targetEl.classList.contains('hidden');
                    targetEl.classList.toggle('hidden');
                    trigger.setAttribute('aria-expanded', isHidden);
                }
            });
        });
    }
}

// Initialize on DOM Load
document.addEventListener('DOMContentLoaded', () => {
    window.techDoc = new TechnicalDocEngine();
});