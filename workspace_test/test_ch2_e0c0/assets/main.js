/**
 * ECG Physics Interactive Engine
 * Chapter 2: From Electrodes to Leads
 */

class ECGDocEngine {
  constructor() {
    this.initTheme();
    this.initReadingProgress();
    this.initTOC();
    this.initCodeBlocks();
    this.initMathJax();
    this.initVectorProjection();
    this.initLeadInteractions();
  }

  // 1. Dark Mode Toggle
  initTheme() {
    const toggle = document.querySelector('#dark-mode-toggle');
    if (!toggle) return;

    const setTheme = (isDark) => {
      document.documentElement.classList.toggle('dark', isDark);
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
    };

    // Check system preference or local storage
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));

    toggle.addEventListener('click', () => {
      const isDark = document.documentElement.classList.contains('dark');
      setTheme(!isDark);
    });
  }

  // 2. Reading Progress Bar
  initReadingProgress() {
    const progressBar = document.querySelector('#reading-progress');
    if (!progressBar) return;

    window.addEventListener('scroll', () => {
      const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
      const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrolled = (winScroll / height) * 100;
      progressBar.style.width = scrolled + "%";
    });
  }

  // 3. Table of Contents with Scroll Spy
  initTOC() {
    const tocContainer = document.querySelector('#toc-list');
    const headers = document.querySelectorAll('article h2, article h3');
    if (!tocContainer || headers.length === 0) return;

    // Generate TOC items
    headers.forEach((header, index) => {
      const id = header.id || `heading-${index}`;
      header.id = id;
      
      const link = document.createElement('a');
      link.href = `#${id}`;
      link.textContent = header.textContent;
      link.className = `toc-link block py-1 text-sm transition-colors ${
        header.tagName === 'H3' ? 'pl-4 text-slate-500' : 'font-semibold text-slate-700'
      }`;
      tocContainer.appendChild(link);
    });

    // Intersection Observer for Scroll Spy
    const observerOptions = { rootMargin: '-100px 0px -70% 0px' };
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          document.querySelectorAll('.toc-link').forEach(link => {
            link.classList.toggle('text-blue-500', link.getAttribute('href') === `#${entry.target.id}`);
          });
        }
      });
    }, observerOptions);

    headers.forEach(header => observer.observe(header));
  }

  // 4. Code Block Utilities (Copy Button)
  initCodeBlocks() {
    const blocks = document.querySelectorAll('pre');
    blocks.forEach(block => {
      const container = document.createElement('div');
      container.className = 'relative group';
      block.parentNode.insertBefore(container, block);
      container.appendChild(block);

      const copyBtn = document.createElement('button');
      copyBtn.innerHTML = 'Copy';
      copyBtn.className = 'absolute top-2 right-2 px-2 py-1 text-xs bg-slate-800 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity';
      
      copyBtn.addEventListener('click', async () => {
        const code = block.querySelector('code').innerText;
        await navigator.clipboard.writeText(code);
        copyBtn.innerText = 'Copied!';
        setTimeout(() => copyBtn.innerText = 'Copy', 2000);
      });

      container.appendChild(copyBtn);
    });
  }

  // 5. MathJax Support Configuration
  initMathJax() {
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']],
        processEscapes: true
      },
      options: {
        enableMenu: false
      },
      chtml: {
        displayAlign: 'center'
      }
    };
  }

  // 6. Vector Projection Demo (Core Physics Logic)
  initVectorProjection() {
    const svg = document.querySelector('#vector-demo-svg');
    const cardiacVector = document.querySelector('#cardiac-vector'); // The red arrow
    const projectionLine = document.querySelector('#projection-shadow'); // Shadow on Lead II
    const ecgPath = document.querySelector('#live-ecg-path'); // Simulated ECG wave
    
    if (!svg || !cardiacVector) return;

    let angle = 0;
    let points = Array(100).fill(0); // For ECG wave history

    const updateProjection = (e) => {
      const rect = svg.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      
      // Calculate angle from center to mouse
      const x = (e.clientX || e.touches[0].clientX) - centerX;
      const y = (e.clientY || e.touches[0].clientY) - centerY;
      angle = Math.atan2(y, x);

      // Rotate Vector Arrow (Red)
      const degrees = (angle * 180) / Math.PI;
      cardiacVector.setAttribute('transform', `rotate(${degrees}, 200, 200)`);

      // Calculate Projection on Lead II (Lead II is at 60 degrees)
      const leadIIAngle = Math.PI / 3; // 60 deg
      const projectionMagnitude = Math.cos(angle - leadIIAngle);
      
      // Update Shadow Visual
      if (projectionLine) {
        const length = projectionMagnitude * 100; // Scale for UI
        projectionLine.setAttribute('x2', 200 + Math.cos(leadIIAngle) * length);
        projectionLine.setAttribute('y2', 200 + Math.sin(leadIIAngle) * length);
      }

      this.drawSimulatedECG(projectionMagnitude);
    };

    svg.addEventListener('mousemove', updateProjection);
    svg.addEventListener('touchmove', (e) => {
      e.preventDefault();
      updateProjection(e);
    }, { passive: false });
  }

  // Helper for Vector Demo: Draws a real-time ECG wave based on current projection
  drawSimulatedECG(amplitude) {
    const canvas = document.querySelector('#ecg-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Shift points and add new amplitude
    this.ecgData = this.ecgData || Array(width).fill(height / 2);
    this.ecgData.shift();
    
    // Simulate a QRS pulse scaled by projection
    const now = Date.now() * 0.005;
    const baseWave = Math.sin(now) > 0.9 ? amplitude * 40 : 0; 
    this.ecgData.push((height / 2) - baseWave);

    ctx.clearRect(0, 0, width, height);
    ctx.beginPath();
    ctx.strokeStyle = '#e11d48';
    ctx.lineWidth = 2;
    
    this.ecgData.forEach((y, x) => {
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  // 7. Hexaxial Lead Interaction
  initLeadInteractions() {
    const leadCards = document.querySelectorAll('.lead-card');
    const svgLeads = document.querySelectorAll('.svg-lead-axis');

    leadCards.forEach(card => {
      card.addEventListener('mouseenter', () => {
        const leadId = card.dataset.lead;
        
        // Highlight corresponding SVG axis
        svgLeads.forEach(axis => {
          if (axis.id === `axis-${leadId}`) {
            axis.classList.add('stroke-blue-500', 'stroke-[3px]');
            axis.classList.remove('stroke-slate-200');
          } else {
            axis.style.opacity = '0.2';
          }
        });

        // Scale card
        card.style.transform = 'scale(1.05)';
        card.classList.add('border-blue-500', 'shadow-lg');
      });

      card.addEventListener('mouseleave', () => {
        svgLeads.forEach(axis => {
          axis.classList.remove('stroke-blue-500', 'stroke-[3px]');
          axis.classList.add('stroke-slate-200');
          axis.style.opacity = '1';
        });
        card.style.transform = 'scale(1)';
        card.classList.remove('border-blue-500', 'shadow-lg');
      });
    });
  }
}

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
  window.ECGEngine = new ECGDocEngine();
});