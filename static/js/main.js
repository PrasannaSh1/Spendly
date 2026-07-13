// main.js — students will add JavaScript here as features are built

document.querySelectorAll(".profile-table-delete-form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
        if (!confirm("Delete this expense? This cannot be undone.")) {
            event.preventDefault();
        }
    });
});
