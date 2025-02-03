document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript Loaded...");

    // Initialize Stripe (Replace with your actual publishable key)
    const stripe = Stripe("pk_test_51Qm6jDDeOdL1UspnNyZtJSMCMGYVnuDmOvFLPcTheGrBoyAYVxVS0GP64qZx2pakARKJ43cEHuirTNSNuPQ2BKai00dEaH9G6D");

    // Select elements
    const addPersonButton = document.getElementById("addPerson");
    const registrantFields = document.getElementById("registrantFields");
    const totalCostSpan = document.getElementById("totalCost");
    const paymentButton = document.getElementById("paymentButton");
    const notification = document.getElementById("notification");

    let registrantCount = 1;
    let totalCost = 0;

    // Function to show notifications
    function showNotification(message, type = "success") {
        notification.textContent = message;
        notification.className = `alert alert-${type}`;
        notification.style.display = "block";

        setTimeout(() => {
            notification.style.display = "none";
        }, 5000);
    }

    // Function to update the total cost
    function updateTotalCost() {
        totalCost = 0;
        document.querySelectorAll(".registrant").forEach(registrantDiv => {
            const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;
            const price = ageGroup === "adult" ? 125 : 50; // Adult: $125, Child: $50
            totalCost += price;
        });

        // Fix double dollar sign issue
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
        `;

        // Ensure price updates when selection changes
        newRegistrantDiv.querySelector(".age-group-select").addEventListener("change", updateTotalCost);

        return newRegistrantDiv;
    }

    // Add initial registrant block and set the price correctly on page load
    registrantFields.appendChild(createRegistrantBlock(registrantCount));
    updateTotalCost();

    // Add Person Button Click Event
    addPersonButton.addEventListener("click", function () {
        registrantCount++;
        registrantFields.appendChild(createRegistrantBlock(registrantCount));
        updateTotalCost(); // Update total when new registrant is added
    });

    // Payment Button Click Event (Checkout)
    paymentButton.addEventListener("click", async () => {
        try {
            let registrants = [];
            let allRegistrantsValid = true;

            document.querySelectorAll(".registrant").forEach(registrantDiv => {
                const name = registrantDiv.querySelector('[name="name"]').value;
                const tshirtSize = registrantDiv.querySelector('[name="tshirtSize"]').value;
                const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;

                if (!name) {
                    allRegistrantsValid = false;
                    registrantDiv.querySelector('[name="name"]').classList.add("is-invalid");
                } else {
                    registrantDiv.querySelector('[name="name"]').classList.remove("is-invalid");
                }

                const price = ageGroup === "adult" ? 125 : 50;
                registrants.push({ name, tshirtSize, ageGroup, price });
            });

            if (!allRegistrantsValid) {
                showNotification("Please enter all registrant names.", "danger");
                return;
            }

            if (registrants.length === 0) {
                showNotification("Please add at least one registrant.", "danger");
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

            const checkoutResponse = await fetch("/create-checkout-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ registrants })
            });

            const checkoutData = await checkoutResponse.json();

            console.log("✅ Checkout session created:", checkoutData.sessionId);

            if (!checkoutResponse.ok || !checkoutData.sessionId) {
                throw new Error("Invalid checkout session");
            }

            await stripe.redirectToCheckout({ sessionId: checkoutData.sessionId });

        } catch (error) {
            console.error("❌ Error during checkout:", error);
            showNotification("Error creating payment session. Please check the console for details.", "danger");
        }
    });
    fetch('/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ registrants: registrants })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.error(data.error);
            // Display error message to the user
        } else {
            fetch('/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({}) // You might not need to send any data here
            })
            .then(response => response.json())
            .then(result => {
                if (result.error) {
                    console.error(result.error);
                    // Display error message to the user
                } else {
                  console.log(result.redirect_url)
                    window.location.href = result.redirect_url; // Use the returned URL
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
});

    // Update total cost on page load
    updateTotalCost();
});
