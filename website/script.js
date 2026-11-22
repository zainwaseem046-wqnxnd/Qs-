// Clearview QS — small enhancements; the site works without JavaScript.
(function () {
  const header = document.querySelector(".site-header");
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("site-nav");

  // Header shadow once the page scrolls
  const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 8);
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Mobile menu
  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    nav.classList.toggle("open", open);
  };
  toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
  nav.addEventListener("click", (e) => { if (e.target.closest("a")) setOpen(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });

  // Current year in footer
  const year = document.getElementById("year");
  if (year) year.textContent = new Date().getFullYear();

  // Gentle reveal of cards as they scroll into view
  const revealables = document.querySelectorAll(".service, .step, .values li, .sectors li");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add("in"); io.unobserve(entry.target); }
      });
    }, { threshold: 0.1 });
    revealables.forEach((el) => { el.classList.add("reveal"); io.observe(el); });
  }

  // Contact form: validate, then open the visitor's email app with the enquiry filled in.
  const form = document.getElementById("contact-form");
  const errorBox = form.querySelector(".form-error");
  const emailLink = document.querySelector("[data-contact-email]");
  const to = emailLink ? emailLink.textContent.trim() : "";

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const missing = [];
    form.querySelectorAll("[required]").forEach((input) => {
      const ok = input.value.trim() !== "" && (input.type !== "email" || /.+@.+\..+/.test(input.value));
      input.classList.toggle("invalid", !ok);
      if (!ok) missing.push(input.closest(".field").querySelector("span").textContent.toLowerCase());
    });
    if (missing.length) {
      errorBox.textContent = "Please add a valid " + missing.join(", ") + ".";
      errorBox.hidden = false;
      return;
    }
    errorBox.hidden = true;

    const subject = "Project enquiry: " + data.get("service");
    const body = [
      "Name: " + data.get("name"),
      "Company: " + (data.get("company") || "-"),
      "Email: " + data.get("email"),
      "Phone: " + (data.get("phone") || "-"),
      "Service: " + data.get("service"),
      "",
      data.get("message"),
    ].join("\n");
    window.location.href = "mailto:" + to + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(body);
  });
})();
