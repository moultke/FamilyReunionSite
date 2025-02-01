document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript Loaded...");

    // Initialize Stripe (Replace with your actual publishable key)
    const stripe = Stripe("pk_test_51Qm6jDDeOdL1UspnNyZtJSMCMGYVnuDmOvFLPcTheGrBoyAYVxVS0GP64qZx2pakARKJ43cEHuirTNSNuPQ2BKai00dEaH9G6D");

    // Select elements
    const addPersonButton = document.getElementById("addPerson");
    const registrantFields = document.getElementById("registrantFields");
    const registrantList = document.getElementById("registrantList"); // This might not be needed, confirm its use
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
            let allRegistrantsValid = true; // Flag to track if all registrants are valid

            document.querySelectorAll(".registrant").forEach(registrantDiv => {
                const name = registrantDiv.querySelector('[name="name"]').value;
                const tshirtSize = registrantDiv.querySelector('[name="tshirtSize"]').value;
                const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;

                if (!name) {
                    allRegistrantsValid = false; // Set the flag to false if a name is missing
                }

                const price = ageGroup === "adult" ? 125 : 50;
                registrants.push({ name, tshirtSize, ageGroup, price });
            });

            if (!allRegistrantsValid) {
                alert("Please enter all registrant names.");
                return;
            }

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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ registrants }) // Pass registrants data
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

    // Function to load gallery images
    function loadGallery(page = 1, perPage = 8) {
        fetch("/images")
            .then(response => response.json())
            .then(data => {
                let images = data.images;
                let galleryGrid = document.getElementById("galleryGrid");
                let pagination = document.getElementById("pagination");

                galleryGrid.innerHTML = "";
                pagination.innerHTML = "";

                let start = (page - 1) * perPage;
                let end = start + perPage;
                let paginatedImages = images.slice(start, end);

                paginatedImages.forEach(imageUrl => {
                    let colDiv = document.createElement("div");
                    colDiv.className = "col-md-3 mb-3";

                    let imgElement = document.createElement("img");
                    imgElement.src = imageUrl;
                    imgElement.className = "img-thumbnail gallery-img";
                    imgElement.setAttribute("data-bs-toggle", "modal");
                    imgElement.setAttribute("data-bs-target", "#imageModal");
                    imgElement.onclick = () => openModal(imageUrl);

                    colDiv.appendChild(imgElement);
                    galleryGrid.appendChild(colDiv);
                });

                // Pagination
                let totalPages = Math.ceil(images.length / perPage);
                for (let i = 1; i <= totalPages; i++) {
                    let pageItem = document.createElement("li");
                    pageItem.className = "page-item " + (i === page ? "active" : "");

                    let pageLink = document.createElement("a");
                    pageLink.className = "page-link";
                    pageLink.href = "#";
                    pageLink.innerText = i;
                    pageLink.onclick = (e) => {
                        e.preventDefault();
                        loadGallery(i);
                    };

                    pageItem.appendChild(pageLink);
                    pagination.appendChild(pageItem);
                }
            })
            .catch(error => console.error("Error loading gallery:", error));
    }

    // Function to open image in modal
    function openModal(imageUrl) {
        document.getElementById("modalImage").src = imageUrl;
    }

    // Function to upload image
    window.uploadImage = async function () {
        let fileInput = document.getElementById("uploadPhoto");
        let file = fileInput.files[0];

        if (!file) {
            alert("Please select an image first.");
            return;
        }

        let formData = new FormData();
        formData.append("file", file);

        try {
            let response = await fetch("/upload", {
                method: "POST",
                body: formData
            });

            let result = await response.json();
            if (response.ok) {
                alert("Image uploaded successfully!");
                fileInput.value = "";
                loadGallery(); // Refresh the gallery
            } else {
                alert(result.error);
            }
        } catch (error) {
            console.error("Upload error:", error);
        }
    };

    // Load the gallery on DOMContentLoaded
    loadGallery();
});