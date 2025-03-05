// Example: Add a confirmation message on form submission
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('rsvpForm');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            alert('Form submitted successfully!');
        });
    }
});