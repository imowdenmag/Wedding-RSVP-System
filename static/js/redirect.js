// Countdown and redirect
let countdown = 5; // Number of seconds before redirect
const countdownElement = document.getElementById('countdown');

const interval = setInterval(() => {
    countdown--;
    countdownElement.textContent = countdown;

    if (countdown === 0) {
        clearInterval(interval);
        window.location.href = "/"; // Redirect to the landing page
    }
}, 1000); // Update every second