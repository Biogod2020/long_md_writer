/**
 * Technical Document Interactive Engine
 * Focus: ECG Physics & Lead Axis Theory
 * 
 * Features: TOC Scroll Spy, Code Utilities, MathJax Config, 
 * Reading Progress, Dark Mode, and Custom ECG Projection Simulator.
 */

class TechnicalDocEngine {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupReadingProgress();
            this.setupDarkMode();
            this.setupTOC();
            this.setupCodeBlocks();
            this.setupMathJax();
            this.initProjectionSimulator();
            this.initHexaxialToggle();
            this.initProgressiveDisclosure();
        });
    }

    /**
     * 1. Reading Progress Bar
     */
    setupReadingProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'fixed top-0 left-0 h-1 bg-sky-500 z-50 transition-all duration-150';
        progressBar.style.width = '0%';
        document.body.appendChild(progressBar);

        window.addEventListener('scroll', () => {
            const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
            const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
            const scrolled = (winScroll / height) * 100;
            progressBar.style.width = scrolled + "%";
        });
    }

    /**
     * 2. Dark Mode Toggle
     */
    setupDarkMode() {
        const toggle = document.querySelector('#dark-mode-toggle');
        if (!toggle) return;

        const setTheme = (isDark) => {
            document.documentElement.classList.toggle('dark', isDark);
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
        };

        toggle.addEventListener('click', () => {
            const isDark = !document.documentElement.classList.contains('dark');
            setTheme(isDark);
        });

        // Init from preference
        if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            setTheme(true);
        }
    }

    /**
     * 3. Table of Contents with Scroll Spy
     */
    setupTOC() {
        const tocContainer = document.querySelector('#toc-content');
        const headings = document.querySelectorAll('article h2, article h3');
        if (!tocContainer || headings.length === 0) return;

        const tocList = document.createElement('ul');
        tocList.className = 'space-y-2 text-sm';

        headings.forEach((heading, index) => {
            const id = `heading-${index}`;
            heading.id = id;

            const li = document.createElement('li');
            li.className = heading.tagName === 'H3' ? 'ml-4' : 'font-medium';
            
            const link = document.createElement('a');
            link.href = `#${id}`;
            link.textContent = heading.textContent;
            link.className = 'text-slate-500 hover:text-sky-600 transition-colors toc-link';
            link.dataset.target = id;

            li.appendChild(link);
            tocList.appendChild(li);
        });

        tocContainer.appendChild(tocList);

        // Intersection Observer for Scroll Spy
        const observerOptions = { rootMargin: '-100px 0px -70% 0px' };
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    document.querySelectorAll('.toc-link').forEach(link => {
                        link.classList.toggle('text-sky-600', link.dataset.target === entry.target.id);
                        link.classList.toggle('font-bold', link.dataset.target === entry.target.id);
                    });
                }
            });
        }, observerOptions);

        headings.forEach(h => observer.observe(h));
    }

    /**
     * 4. Code Block Utilities
     */
    setupCodeBlocks() {
        document.querySelectorAll('pre').forEach(block => {
            const container = document.createElement('div');
            container.className = 'relative group';
            block.parentNode.insertBefore(container, block);
            container.appendChild(block);

            const copyBtn = document.createElement('button');
            copyBtn.className = 'absolute top-2 right-2 p-1 rounded bg-slate-800 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity text-xs';
            copyBtn.innerHTML = 'Copy';

            copyBtn.addEventListener('click', async () => {
                const code = block.querySelector('code').innerText;
                await navigator.clipboard.writeText(code);
                copyBtn.innerText = 'Copied!';
                setTimeout(() => copyBtn.innerText = 'Copy', 2000);
            });

            container.appendChild(copyBtn);
        });
    }

    /**
     * 5. Math Rendering Support (MathJax Configuration)
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
    }

    /**
     * 6. Custom Element: Projection Simulator
     * Logic for the rotating Cardiac Vector P and its projection on Lead I
     */
    initProjectionSimulator() {
        const svg = document.querySelector('#projection-sim');
        if (!svg) return;

        const vectorP = svg.querySelector('#cardiac-vector');
        const projectionLine = svg.querySelector('#projection-shadow');
        const ecgPath = svg.querySelector('#ecg-trace');
        
        let angle = 0;
        const ecgData = [];
        const maxDataPoints = 100;

        const update = () => {
            // 1. Rotate Vector P
            angle += 0.02;
            const length = 60;
            const x = Math.cos(angle) * length;
            const y = Math.sin(angle) * length;
            
            if (vectorP) {
                vectorP.setAttribute('x2', 200 + x);
                vectorP.setAttribute('y2', 100 + y);
            }

            // 2. Calculate Projection (Shadow on Lead I)
            // V = |P| * cos(theta)
            const projectionWidth = x; 
            if (projectionLine) {
                projectionLine.setAttribute('x1', 200);
                projectionLine.setAttribute('x2', 200 + projectionWidth);
            }

            // 3. Update ECG Trace
            ecgData.push(projectionWidth / 2); // Scale for display
            if (ecgData.length > maxDataPoints) ecgData.shift();

            if (ecgPath) {
                const pathD = ecgData.map((val, i) => {
                    const xPos = 50 + (i * (300 / maxDataPoints));
                    const yPos = 170 - val; // 170 is baseline
                    return `${i === 0 ? 'M' : 'L'} ${xPos} ${yPos}`;
                }).join(' ');
                ecgPath.setAttribute('d', pathD);
            }

            requestAnimationFrame(update);
        };

        update();
    }

    /**
     * 7. Custom Element: Hexaxial Toggle Logic
     */
    initHexaxialToggle() {
        const leads = document.querySelectorAll('.hexaxial-lead');
        const infoPanel = document.querySelector('#lead-info-panel');

        const leadData = {
            'aVL': { region: 'Lateral Wall', artery: 'LCx', color: '#0ea5e9' },
            'II': { region: 'Inferior Wall', artery: 'RCA', color: '#e11d48' },
            'I': { region: 'Lateral Wall', artery: 'LCx/LAD', color: '#0ea5e9' }
        };

        leads.forEach(lead => {
            lead.addEventListener('mouseenter', (e) => {
                const leadId = e.target.dataset.lead;
                const data = leadData[leadId];
                if (data && infoPanel) {
                    infoPanel.innerHTML = `
                        <div class="p-4 border-l-4" style="border-color: ${data.color}">
                            <h4 class="font-bold text-slate-900">${leadId} Lead</h4>
                            <p class="text-sm">Region: ${data.region}</p>
                            <p class="text-sm">Artery: ${data.artery}</p>
                        </div>
                    `;
                    e.target.style.strokeWidth = "4";
                }
            });

            lead.addEventListener('mouseleave', (e) => {
                e.target.style.strokeWidth = "2";
            });
        });
    }

    /**
     * 8. Custom Element: Progressive Disclosure (3D Chest Peel)
     */
    initProgressiveDisclosure() {
        const peelTrigger = document.querySelector('#peel-skin-btn');
        const skinLayer = document.querySelector('#chest-skin-layer');

        if (peelTrigger && skinLayer) {
            peelTrigger.addEventListener('click', () => {
                const isHidden = skinLayer.style.opacity === '0';
                skinLayer.style.opacity = isHidden ? '1' : '0';
                skinLayer.style.transition = 'opacity 0.8s ease-in-out';
                peelTrigger.textContent = isHidden ? 'Peel Skin' : 'Restore Skin';
            });
        }
    }
}

// Initialize the engine
const docEngine = new TechnicalDocEngine();