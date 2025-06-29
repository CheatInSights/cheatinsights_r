// Add click handler to document to clear highlights when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.classList.contains('run')) {
        document.querySelectorAll('.run').forEach(run => {
            run.style.border = '';
            run.style.backgroundColor = '';
            run.style.borderRadius = '';
            run.style.padding = '';
        });
    }
});

// Rotating Words Functionality
document.addEventListener('DOMContentLoaded', function() {
    initializeRotatingWords();
});

function initializeRotatingWords() {
    const wordLeft = document.getElementById('wordLeft');
    const wordRight = document.getElementById('wordRight');
    
    if (!wordLeft || !wordRight) {
        console.log('Rotating words elements not found');
        return;
    }

    // Word lists for rotation - X and Y axis metrics for graphs
    const leftWords = [
        'RSID Frequency',
        'Editing Sessions',
        'Revision Count',
        'Character Count',
        'Word Count',
    ];

    const rightWords = [
        'Word Count',
        'Character Count',
        'Editing Sessions',
        'RSID Frequency',
        'Sentence Count',
        'Paragraph Count',
        'Revision Count',
    ];

    let leftIndex = 0;
    let rightIndex = 0;
    let leftAnimating = false;
    let rightAnimating = false;

    function rotateLeftWord() {
        if (leftAnimating) return;
        leftAnimating = true;

        // Fade out current word (goes up)
        wordLeft.classList.add('fade-out');

        setTimeout(() => {
            // Update word and set initial position below
            leftIndex = (leftIndex + 1) % leftWords.length;
            wordLeft.textContent = leftWords[leftIndex];
            wordLeft.style.transform = 'translateY(20px)';
            wordLeft.style.opacity = '0';

            // Fade in new word (comes from below)
            wordLeft.classList.remove('fade-out');
            wordLeft.classList.add('fade-in');

            setTimeout(() => {
                wordLeft.classList.remove('fade-in');
                wordLeft.style.transform = '';
                wordLeft.style.opacity = '';
                leftAnimating = false;
            }, 500);
        }, 500);
    }

    function rotateRightWord() {
        if (rightAnimating) return;
        rightAnimating = true;

        // Fade out current word (goes up)
        wordRight.classList.add('fade-out');

        setTimeout(() => {
            // Update word and set initial position below
            rightIndex = (rightIndex + 1) % rightWords.length;
            wordRight.textContent = rightWords[rightIndex];
            wordRight.style.transform = 'translateY(20px)';
            wordRight.style.opacity = '0';

            // Fade in new word (comes from below)
            wordRight.classList.remove('fade-out');
            wordRight.classList.add('fade-in');

            setTimeout(() => {
                wordRight.classList.remove('fade-in');
                wordRight.style.transform = '';
                wordRight.style.opacity = '';
                rightAnimating = false;
            }, 500);
        }, 500);
    }

    // Start rotation at different intervals
    setInterval(rotateLeftWord, 1000);  // Left word every 3 seconds
    setInterval(rotateRightWord, 1000);  // Right word every 0.8 seconds (faster)
}

// Cursor tracking for interactive dots
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing interactive dots...');
    initializeInteractiveDots();
});

function initializeInteractiveDots() {
    const graphsSection = document.querySelector('.graphs-section');
    
    if (!graphsSection) {
        console.log('Graphs section not found');
        return;
    }

    console.log('Graphs section found, creating overlay...');

    // Create interactive dots overlay
    const dotsOverlay = document.createElement('div');
    dotsOverlay.className = 'interactive-dots-overlay';
    dotsOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: radial-gradient(circle, rgba(255, 0, 0, 0.4) 2px, transparent 2px);
        background-size: 40px 40px;
        background-position: 0 0, 20px 20px;
        pointer-events: none;
        z-index: 1;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    graphsSection.appendChild(dotsOverlay);
    console.log('Overlay created and appended');

    let isHovering = false;
    let mouseX = 0;
    let mouseY = 0;
    const radius = 150; // Increased radius in pixels

    graphsSection.addEventListener('mouseenter', function() {
        console.log('Mouse entered graphs section');
        isHovering = true;
        dotsOverlay.style.opacity = '1';
    });

    graphsSection.addEventListener('mouseleave', function() {
        console.log('Mouse left graphs section');
        isHovering = false;
        dotsOverlay.style.opacity = '0';
    });

    graphsSection.addEventListener('mousemove', function(e) {
        if (!isHovering) return;
        
        const rect = graphsSection.getBoundingClientRect();
        mouseX = e.clientX - rect.left;
        mouseY = e.clientY - rect.top;

        // Create a mask that shows red dots only near the cursor
        const maskGradient = `radial-gradient(circle ${radius}px at ${mouseX}px ${mouseY}px, rgba(255, 255, 255, 1) 0%, transparent ${radius}px)`;
        dotsOverlay.style.webkitMaskImage = maskGradient;
        dotsOverlay.style.maskImage = maskGradient;
    });

    console.log('Event listeners attached');
}