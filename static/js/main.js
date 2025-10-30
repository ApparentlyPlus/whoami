/* --- Navigation Toggle --- */
// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
// ... existing navigation toggle code ...
    const menuToggleBtn = document.getElementById('menu-toggle-btn');
    const mainMenu = document.getElementById('main-menu');

    if (menuToggleBtn && mainMenu) {
        menuToggleBtn.addEventListener('click', () => {
            // Toggle the 'is-active' class on both the button and the menu
            menuToggleBtn.classList.toggle('is-active');
            mainMenu.classList.toggle('is-active');

            // Update ARIA attribute for accessibility
            const isExpanded = menuToggleBtn.getAttribute('aria-expanded') === 'true';
            menuToggleBtn.setAttribute('aria-expanded', !isExpanded);
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

// ... existing terminal magic code ...
var TE = TerminalEmulator.init(document.getElementById('screen'));

TE.wait(1000, false)
  .then( TE.enterInput.bind(TE, 'whoami') )
  .then( TE.enterCommand.bind( TE ) )
  .then( TE.enterResponse.bind(TE, 'Panagiotis Chatzikallias (aka ApparentlyPlus)') )
  .then( TE.wait.bind(TE, 1000, false) )
  .then( TE.enterInput.bind(TE, 'bash whatAreMyInterests.sh') )
  .then( TE.enterCommand.bind(TE) )
  .then( TE.enterResponse.bind(TE, 'Backend Development, Systems Design, Cybersecurity, Compilers') )
  .then( TE.wait.bind(TE, 1000, false) )
  .then( TE.enterInput.bind(TE, 'bash FavoriteLanguages.sh') )
  .then( TE.enterCommand.bind(TE) )
  .then( TE.enterResponse.bind(TE, 'Python, C, Rust, Go') )
  .then( TE.wait.bind(TE, 1000, false) )
  .then( TE.enterInput.bind(TE, 'cat recruiter_note.txt') )
  .then( TE.enterCommand.bind(TE) )
  .then( TE.enterResponse.bind(TE, 'This website serves as my interactive autobiography. Welcome.') )
  .then( TE.reset.bind(TE) );


/* --- NEW PARTICLES.JS CONFIG --- */

document.addEventListener('DOMContentLoaded', () => {
  particlesJS('particles-js', {
    "particles": {
      "number": {
        "value": 60, // Not too many
        "density": {
          "enable": true,
          "value_area": 800
        }
      },
      "color": {
        "value": "#0f0" // Your neon green
      },
      "shape": {
        "type": "circle"
      },
      "opacity": {
        "value": 0.4, // Dim
        "random": true, // Random opacity
        "anim": {
          "enable": true, // Enable flickering
          "speed": 0.8,
          "opacity_min": 0.05,
          "sync": false
        }
      },
      "size": {
        "value": 2,
        "random": true,
        "anim": {
          "enable": false
        }
      },
      "line_linked": {
        "enable": true, // Enable connecting lines
        "distance": 150,
        "color": "#0f0", // Neon green
        "opacity": 0.1, // Very dim lines
        "width": 1
      },
      "move": {
        "enable": true,
        "speed": 0.5, // Move slowly
        "direction": "none",
        "random": true,
        "straight": false,
        "out_mode": "out",
        "bounce": false
      }
    },
    "interactivity": {
      "detect_on": "canvas",
      "events": {
        "onhover": {
          "enable": false // No interactivity
        },
        "onclick": {
          "enable": false
        },
        "resize": true
      }
    },
    "retina_detect": true
  });
});

