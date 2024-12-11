document.addEventListener("DOMContentLoaded", function () {
  initializeHamburgerMenu();
});

function initializeHamburgerMenu() {
  var hamburger = document.querySelector(".hamburger");
  var menu = document.querySelector(".sidenav");

  if (hamburger && menu) {
    hamburger.addEventListener("click", function () {
      hamburger.classList.toggle("is-active");
      menu.classList.toggle("visible");
    });
  }
}
