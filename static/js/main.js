/* --- Navigation Toggle & Animations --- */
document.addEventListener('DOMContentLoaded', () => {
	// --- Navigation Toggle ---
	const menuToggleBtn = document.getElementById('menu-toggle-btn');
	const mainMenu = document.getElementById('main-menu');
	const pageOverlay = document.getElementById('page-overlay'); // Get the overlay

	// Check if all elements exist
	if (menuToggleBtn && mainMenu && pageOverlay) {
		
		// Toggle menu on button click
		menuToggleBtn.addEventListener('click', () => {
			menuToggleBtn.classList.toggle('is-active');
			mainMenu.classList.toggle('is-active');
			pageOverlay.classList.toggle('is-active'); // Toggle overlay
			
			const isExpanded = menuToggleBtn.getAttribute('aria-expanded') === 'true';
			menuToggleBtn.setAttribute('aria-expanded', !isExpanded);
		});

		// Close menu when clicking the overlay
		pageOverlay.addEventListener('click', () => {
			menuToggleBtn.classList.remove('is-active');
			mainMenu.classList.remove('is-active');
			pageOverlay.classList.remove('is-active');
			menuToggleBtn.setAttribute('aria-expanded', 'false');
		});
	}

    // --- Landing Page Animation ---
    const landingGrid = document.getElementById('landing-grid');

    if (landingGrid) {
        const terminalScreen = document.querySelector('#landing-terminal .screen');

        // 1. Start the initial fade-in/pop-in animation
        document.body.classList.add('animation-running');

        // 2. Start the terminal typing animation after its CSS pop-in delay
        setTimeout(() => {
            startTerminalAnimation();
        }, 2400); // 2400ms = 2.4s
    }


    // --- Particles.js Config ---
    // Make sure the particles-js div exists
    if (document.getElementById('particles-js')) {
        particlesJS('particles-js', {
            "particles": {
                "number": { "value": 60, "density": { "enable": true, "value_area": 800 } },
                "color": { "value": "#0f0" },
                "shape": { "type": "circle" },
                "opacity": { "value": 0.4, "random": true, "anim": { "enable": true, "speed": 0.8, "opacity_min": 0.05, "sync": false } },
                "size": { "value": 2, "random": true, "anim": { "enable": false } },
                "line_linked": { "enable": true, "distance": 150, "color": "#0f0", "opacity": 0.1, "width": 1 },
                "move": { "enable": true, "speed": 0.5, "direction": "none", "random": true, "straight": false, "out_mode": "out", "bounce": false }
            },
            "interactivity": {
                "detect_on": "canvas",
                "events": { "onhover": { "enable": false }, "onclick": { "enable": false }, "resize": true }
            },
            "retina_detect": true
        });
    }
});

/* --- Terminal Emulator Code Below --- */

var TerminalEmulator = {
// ... existing TerminalEmulator object code ...
  init: function(screen) {
    var inst = Object.create(this);
    inst.screen = screen;
    inst.createInput();
    
    return inst;
  },

  createInput: function() {
    var inputField = document.createElement('div');
    var inputWrap = document.createElement('div');
    
    inputField.className = 'terminal_emulator__field';
    inputField.innerHTML = '';
    inputWrap.appendChild(inputField);
    this.screen.appendChild(inputWrap);
    this.field = inputField;
    this.fieldwrap = inputWrap;
  },


  enterInput: function(input) {
    return new Promise( (resolve, reject) => {
    var randomSpeed = (max, min) => { 
      return Math.random() * (max - min) + min; 
    }
      
    var speed = randomSpeed(70, 90);
    var i = 0;
    var str = '';
    var type = () => {
      
      str = str + input[i];
      this.field.innerHTML = str.replace(/ /g, '&nbsp;');
      i++;
      
      setTimeout( () => {
        if( i < input.length){
          if( i % 5 === 0) speed = randomSpeed(80, 120);
          type();
        }else {
          setTimeout( () => {
            resolve();
          }, 400);
          
        } 
      }, speed);
      
      
    };
    
    
    type();
      
    });
  },
  
  enterCommand: function() {
    return new Promise( (resolve, reject ) => {
      var resp = document.createElement('div');
      resp.className = 'terminal_emulator__command';
      resp.innerHTML = this.field.innerHTML;
      this.screen.insertBefore( resp, this.fieldwrap);
      
      this.field.innerHTML = '';
      resolve();
    })
  },

  enterResponse: function(response) {
    
    return new Promise( (resolve, reject ) => {
      var resp = document.createElement('div');
      resp.className = 'terminal_emulator__response';
      resp.innerHTML = response;
      this.screen.insertBefore( resp, this.fieldwrap);
      
      resolve();
    })
  
    
  },
  
  wait : function( time, busy ) {
    busy = (busy === undefined ) ? true : busy;
    return new Promise( (resolve, reject) => {
        if (busy){
          this.field.classList.add('waiting');
        } else {
          this.field.classList.remove('waiting');
        }
        setTimeout( () => {
          resolve();
      }, time);
    });
  },
  
  reset : function() {
    return new Promise( (resolve, reject) => {
      this.field.classList.remove('waiting');
      resolve();
    });
  }
};


/*
 * * This is where the magic happens
 *
 */ 

// We must initialize the terminal emulator object first
// We check if the 'screen' element exists before init
const terminalScreenElement = document.getElementById('screen');
var TE;
if (terminalScreenElement) {
    TE = TerminalEmulator.init(terminalScreenElement);
}
// This function will be called by the animation orchestrator
function startTerminalAnimation() {
    if (TE) {
        TE.wait(TE.wait.bind(TE, 500, false)) // Short delay after page load
          .then(TE.enterInput.bind(TE, 'whoami'))
          .then(TE.enterCommand.bind(TE))
          .then(TE.enterResponse.bind(TE, 'Panagiotis Chatzikallias (aka ApparentlyPlus)'))
          .then(TE.wait.bind(TE, 1000, true))
          
          .then(TE.enterInput.bind(TE, 'cat ./core_competencies.txt'))
          .then(TE.enterCommand.bind(TE))
          .then(TE.enterResponse.bind(TE, 'Systems Programming (Kernels, Optimization, Distributed systems), Full-Stack Dev (React, ASP.NET, MongoDB, SQL), Cloud & DevOps (Docker, CI/CD)'))
          .then(TE.wait.bind(TE, 1000, true))

          .then(TE.enterInput.bind(TE, 'ls ./top_projects'))
          .then(TE.enterCommand.bind(TE))
          .then(TE.enterResponse.bind(TE, 'GatOS (Modular Kernel Toolchain), UniNotes (Full-Stack Collab Platform), Marina (Reflective PE Loader)'))
          .then(TE.wait.bind(TE, 1000, true))

          .then(TE.enterInput.bind(TE, 'cat ./fav_lang.txt'))
          .then(TE.enterCommand.bind(TE))
          .then(TE.enterResponse.bind(TE, "Java, C, Python, C# and whatever fits the architecture best!"))

          .then(TE.enterInput.bind(TE, 'bash ./check_distinctions.sh'))
          .then(TE.enterCommand.bind(TE))
          .then(TE.enterResponse.bind(TE, 'ICPC Regional Finalist (2025) | ECSC National Team (2023, Rank 3rd) | HTB Challenge Creator'))
          .then(TE.wait.bind(TE, 1000, true))
          
          .then(TE.reset.bind(TE)); // Loop the animation
    }
}
