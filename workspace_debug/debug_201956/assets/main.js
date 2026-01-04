/**
 * ECG Interactive Document Engine
 * Features: TOC ScrollSpy, Code Utilities, MathJax Config, 
 * Reading Progress, Dark Mode, and Medical Vector Simulators.
 */

class ECGDocEngine {
    constructor() {
        this.state = {
            isDarkMode: window.matchMedia('(prefers-color-scheme: dark)').matches,
            cardiacAngle: 0, // Degrees
            activePlane: 'frontal' // 'frontal' or 'horizontal'
        };

        this.init();
    }

    init() {
        this.initDarkMode();
        this.initReadingProgress();
        this.initTOC();
        this.initCodeBlocks();
        this.initMathJax();
        
        // Custom Medical Interactivity
        this.initVectorSimulator();
        this.initHexaxialSystem();
        this.initPlaneToggle();
    }

    /**
     * 1. Table of Contents with Scroll Spy
     */
    initTOC() {
        const tocContainer = document.querySelector('#toc');
        const headings = document.querySelectorAll('.ecg-h1, .ecg-h2, .ecg-h3');
        if (!tocContainer || headings.length === 0) return;

        const tocList = document.createElement('ul');
        tocList.className = 'toc-list';

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
        const observerOptions = { rootMargin: '-100px 0px -70% 0px' };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    document.querySelectorAll('.toc-item a').forEach(el => el.classList.remove('active'));
                    const activeLink = document.querySelector(`.toc-item a[href="#${entry.target.id}"]`);
                    if (activeLink) activeLink.classList.add('active');
                }
            });
        }, observerOptions);

        headings.forEach(h => observer.observe(h));
    }

    /**
     * 2. Code Block Utilities (Copy Button)
     */
    initCodeBlocks() {
        document.querySelectorAll('pre').forEach(block => {
            const button = document.createElement('button');
            button.className = 'copy-btn';
            button.innerText = 'Copy';
            
            button.addEventListener('click', () => {
                const code = block.querySelector('code').innerText;
                navigator.clipboard.writeText(code).then(() => {
                    button.innerText = 'Copied!';
                    setTimeout(() => button.innerText = 'Copy', 2000);
                });
            });

            block.style.position = 'relative';
            block.appendChild(button);
        });
    }

    /**
     * 3. Math Rendering Support (MathJax Configuration)
     */
    initMathJax() {
        window.MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\(', '\\)']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']],
                processEscapes: true
            },
            svg: { fontCache: 'global' }
        };
        
        // Load MathJax Script dynamically if not present
        if (!document.getElementById('MathJax-script')) {
            const script = document.createElement('script');
            script.id = 'MathJax-script';
            script.async = true;
            script.src = 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js';
            document.head.appendChild(script);
        }
    }

    /**
     * 4. Reading Progress Bar
     */
    initReadingProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'reading-progress-bar';
        document.body.appendChild(progressBar);

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + "%";
        });
    }

    /**
     * 5. Dark Mode Toggle
     */
    initDarkMode() {
        const toggleBtn = document.querySelector('#theme-toggle');
        const applyTheme = (isDark) => {
            document.documentElement.classList.toggle('dark', isDark);
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        };

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                this.state.isDarkMode = !this.state.isDarkMode;
                applyTheme(this.state.isDarkMode);
            });
        }

        // Check local storage
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme) applyTheme(savedTheme === 'dark');
    }

    /**
     * 6. Custom: Vector Projection Simulator (Section 6)
     * Logic: Dot product of Cardiac Vector and Lead Axis
     */
    initVectorSimulator() {
        const svg = document.querySelector('#vector-sim-svg');
        const cardiacVector = document.querySelector('#cardiac-vector');
        const ecgWavePath = document.querySelector('#ecg-realtime-path');
        
        if (!svg || !cardiacVector) return;

        const updateProjection = (angleRad) => {
            const leadAngle = Math.PI / 6; // Lead II is at 60 degrees
            const theta = angleRad - leadAngle;
            const projection = Math.cos(theta); // Dot product P·L
            
            // Update UI Elements
            const amplitude = projection * 50; // Scale for visual
            this.updateECGPreview(amplitude);
            
            // Rotate the visual vector
            cardiacVector.setAttribute('transform', `rotate(${angleRad * (180/Math.PI)}, 100, 100)`);
        };

        svg.addEventListener('mousemove', (e) => {
            if (e.buttons !== 1) return; // Only drag on click
            const rect = svg.getBoundingClientRect();
            const x = e.clientX - rect.left - 100;
            const y = e.clientY - rect.top - 100;
            const angle = Math.atan2(y, x);
            updateProjection(angle);
        });
    }

    updateECGPreview(amplitude) {
        const previewBar = document.querySelector('#projection-amplitude-bar');
        if (previewBar) {
            previewBar.style.height = `${Math.abs(amplitude)}px`;
            previewBar.style.backgroundColor = amplitude >= 0 ? '#0ea5e9' : '#e11d48';
        }
    }

    /**
     * 7. Custom: Hexaxial Reference System (Section 4)
     * Logic: Hover lead -> Highlight anatomical region
     */
    initHexaxialSystem() {
        const leads = document.querySelectorAll('.hexaxial-lead');
        const regions = document.querySelectorAll('.heart-region');

        leads.forEach(lead => {
            lead.addEventListener('mouseenter', () => {
                const targetRegion = lead.dataset.region; // e.g., "inferior"
                regions.forEach(r => {
                    r.classList.toggle('highlight', r.id === targetRegion);
                });
            });

            lead.addEventListener('mouseleave', () => {
                regions.forEach(r => r.classList.remove('highlight'));
            });
        });
    }

    /**
     * 8. Custom: 3D Plane Toggle (Section 5)
     * Logic: Toggle perspective between Frontal and Horizontal
     */
    initPlaneToggle() {
        const toggleBtn = document.querySelector('#plane-toggle-btn');
        const viewport = document.querySelector('#anatomical-viewport');

        if (!toggleBtn || !viewport) return;

        toggleBtn.addEventListener('click', () => {
            this.state.activePlane = this.state.activePlane === 'frontal' ? 'horizontal' : 'frontal';
            
            if (this.state.activePlane === 'horizontal') {
                viewport.style.transform = 'rotateX(60deg) rotateZ(-20deg)';
                toggleBtn.textContent = 'Switch to Frontal Plane';
            } else {
                viewport.style.transform = 'rotateX(0deg) rotateZ(0deg)';
                toggleBtn.textContent = 'Switch to Horizontal Plane';
            }
        });
    }
}

// Initialize on DOM Content Loaded
document.addEventListener('DOMContentLoaded', () => {
    window.ecgEngine = new ECGDocEngine();
});