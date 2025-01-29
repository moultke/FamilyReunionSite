document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript Loaded...");

    // Initialize Stripe (Replace with your actual publishable key)
    const stripe = Stripe("pk_test_51Qm6jDDeOdL1UspnNyZtJSMCMGYVnuDmOvFLPcTheGrBoyAYVxVS0GP64qZx2pakARKJ43cEHuirTNSNuPQ2BKai00dEaH9G6D");

    // Select elements
    const addPersonButton = document.getElementById("addPerson");
    const registrantFields = document.getElementById("registrantFields");
    const registrantList = document.getElementById("registrantList");
    const totalCostSpan = document.getElementById("totalCost");
    const paymentButton = document.getElementById("paymentButton");

    let registrantCount = 1;
    let totalCost = 0;

    // Function to update the total cost
    function updateTotalCost() {
        totalCost = 0;
        document.querySelectorAll(".registrant").forEach(registrantDiv => {
            const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;
            const price = ageGroup === "adult" ? 125 : 50; // Adult: 125, Child: 50
            totalCost += price;
        });

        // Ensure single $ symbol and update UI
        totalCostSpan.textContent = `$${totalCost.toFixed(2)}`;
    }

    // Function to create a registrant block
    function createRegistrantBlock(count) {
        const newRegistrantDiv = document.createElement("div");
        newRegistrantDiv.classList.add("registrant", "border", "p-3", "mb-3");
        newRegistrantDiv.innerHTML = `
            <div class="mb-3">
                <label for="name${count}" class="form-label">Name</label>
                <input type="text" class="form-control" id="name${count}" name="name" required>
            </div>
            <div class="mb-3">
                <label for="tshirtSize${count}" class="form-label">T-Shirt Size</label>
                <select class="form-select" id="tshirtSize${count}" name="tshirtSize">
                    <option value="S">S</option>
                    <option value="M">M</option>
                    <option value="L">L</option>
                    <option value="XL">XL</option>
                    <option value="XXL">XXL</option>
                </select>
            </div>
            <div class="mb-3">
                <label for="ageGroup${count}" class="form-label">Age Group</label>
                <select class="form-select age-group-select" id="ageGroup${count}" name="ageGroup">
                    <option value="adult">Adult ($125)</option>
                    <option value="child">Child ($50)</option>
                </select>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-registrant">Remove</button>
        `;

        // Add event listener to update price on selection change
        newRegistrantDiv.querySelector(".age-group-select").addEventListener("change", updateTotalCost);

        return newRegistrantDiv;
    }

    // Ensure only ONE initial registrant
    registrantFields.innerHTML = "";  // Clear any extra registrants
    registrantFields.appendChild(createRegistrantBlock(registrantCount));

    // Add Person Button Click Event
    addPersonButton.addEventListener("click", function () {
        registrantCount++;
        registrantFields.appendChild(createRegistrantBlock(registrantCount));
        updateTotalCost(); // Update total when new registrant is added
    });

    // Event listener to remove registrants and update total cost
    registrantFields.addEventListener("click", function (event) {
        if (event.target.classList.contains("remove-registrant")) {
            event.target.closest(".registrant").remove();
            updateTotalCost();
        }
    });

    // Payment Button Click Event
    paymentButton.addEventListener("click", async () => {
        try {
            let registrants = [];
            document.querySelectorAll(".registrant").forEach(registrantDiv => {
                const name = registrantDiv.querySelector('[name="name"]').value;
                const tshirtSize = registrantDiv.querySelector('[name="tshirtSize"]').value;
                const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;

                if (!name) {
                    alert("Please enter all registrant names.");
                    return;
                }

                const price = ageGroup === "adult" ? 125 : 50;
                registrants.push({ name, tshirtSize, ageGroup, price });
            });

            if (registrants.length === 0) {
                alert("Please add at least one registrant.");
                return;
            }

            console.log("📌 Sending registration data:", registrants);

            const registerResponse = await fetch("/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ registrants })
            });

            const registerData = await registerResponse.json();

            if (!registerResponse.ok) {
                throw new Error(registerData.error || "Registration failed.");
            }

            console.log("✅ Registration successful. Proceeding to checkout...");

            // Create Checkout Session
            const checkoutResponse = await fetch("/create-checkout-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });

            const checkoutData = await checkoutResponse.json();

            if (!checkoutResponse.ok) {
                throw new Error(checkoutData.error || "Failed to create checkout session.");
            }

            console.log("✅ Checkout session created:", checkoutData.id);

            // Redirect to Stripe Checkout
            const result = await stripe.redirectToCheckout({ sessionId: checkoutData.id });

            if (result.error) {
                console.error("Stripe Checkout Error:", result.error);
                alert(result.error.message);
            }
        } catch (error) {
            console.error("❌ Error during checkout:", error);
            alert("Error creating payment session. Please check the console for details.");
        }
    });

    // Countdown Timer Fix
    const countdownDisplay = document.getElementById("countdown-timer");

    if (!countdownDisplay) {
        console.error("❌ Error: Countdown timer element not found in the DOM!");
    } else {
        const targetDate = new Date("2025-07-17T00:00:00").getTime();

        function updateCountdown() {
            const now = new Date().getTime();
            const timeLeft = targetDate - now;

            if (timeLeft <= 0) {
                countdownDisplay.innerHTML = "🎉 Reunion Time!";
                clearInterval(countdownInterval); // Stop the countdown
                return;
            }

            const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            countdownDisplay.innerHTML = `<strong>${days}d ${hours}h ${minutes}m ${seconds}s</strong>`;
        }

        updateCountdown();
        const countdownInterval = setInterval(updateCountdown, 1000);
    }

    // Update total cost initially
    updateTotalCost();
});
