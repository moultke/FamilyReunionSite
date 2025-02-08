// Define openImageModal in the global scope (outside DOMContentLoaded)
function openImageModal(imageUrl) {
    document.getElementById("modalImage").src = imageUrl;
    const imageModal = new bootstrap.Modal(document.getElementById("imageModal"));
    imageModal.show();
}


document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript Loaded...");

    // Ensure attendeeTicker exists before running anything
    const attendeeTickerContainer = document.getElementById("attendeeTicker");
    // Gallery variables
    const galleryGrid = document.getElementById("galleryGrid");
    const uploadPhoto = document.getElementById("uploadPhoto");
    const galleryNotification = document.getElementById("galleryNotification");
    const baseUrl = window.location.origin;
    // Registration/Payment variables
    const stripe = Stripe("pk_test_51Qm6jDDeOdL1UspnNyZtJSMCMGYVnuDmOvFLPcTheGrBoyAYVxVS0GP64qZx2pakARKJ43cEHuirTNSNuPQ2BKai00dEaH9G6D"); // Replace with your publishable key
    const addPersonButton = document.getElementById("addPerson");
    const registrantFields = document.getElementById("registrantFields");
    const totalCostSpan = document.getElementById("totalCost");
    const paymentButton = document.getElementById("paymentButton");
    const registrationNotification = document.getElementById("registrationNotification");
    // Countdown Timer Code:
    const countdownTimer = document.getElementById('countdown-timer');
    const reunionDate = new Date('2025-07-17T00:00:00'); // Set your reunion date and time
    // RSVP Form Handling
    const rsvpForm = document.getElementById('rsvpForm');
    //    const attendeeTicker = document.getElementById('attendeeTicker').querySelector('.ticker');
    // Check if attendeeTicker exists before accessing it
    //    const attendeeTickerContainer = document.getElementById("attendeeTicker");
    const attendeeTicker = attendeeTickerContainer ? attendeeTickerContainer.querySelector(".ticker") : null;
    //contact form:
    const contactForm = document.getElementById("contactForm");

    let registrantCount = 1;
    let totalCost = 0;
    let currentPage = 1;
    let imagesPerPage = 10;
    let totalImages = 0;
    let pagination;



    contactForm.addEventListener("submit", function (event) {
        event.preventDefault();

        const formData = new FormData(contactForm);

        fetch("/contact", {
            method: "POST",
            body: formData,
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("Message sent successfully!");
                contactForm.reset();
            } else {
                alert("Error sending message. Please try again.");
            }
        })
        .catch(error => {
            console.error("Error:", error);
            alert("An error occurred. Please try again.");
        });
    });

     if (!attendeeTicker) {
        console.error("⚠️ Error: attendeeTicker not found in the DOM.");
        return; // Stop execution to prevent further errors
    }


    rsvpForm.addEventListener('submit', function (event) {
        event.preventDefault();
        const name = document.getElementById('rsvpName').value;
        const email = document.getElementById('rsvpEmail').value;
        const phone = document.getElementById('rsvpPhone').value; // Get phone number
        const attending = document.getElementById('rsvpAttending').value;


        // Send RSVP data to server
        fetch('/rsvp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, email, phone, attending }) // Include phone number
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Update attendee ticker
                    addAttendeeToTicker(name);
                    rsvpForm.reset(); // Clear the form
                    alert("Thank you for your RSVP!"); // Or use a nicer notification
                } else {
                    alert(data.error || "Error submitting RSVP. Please try again.");
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert("An error occurred. Please try again later.");
            });
    });


    function fetchAttendees() {
    fetch('/attendees', { cache: 'no-store' })  // Ensure fresh data
        .then(response => response.json())
        .then(attendees => {
            console.log("✅ Fetching attendees from database:", attendees);

            const attendeeTicker = document.querySelector(".ticker");
            attendeeTicker.innerHTML = ""; // Clear previous attendees

            if (!attendees || attendees.length === 0) {
                console.log("⚠️ No attendees found in database.");
                attendeeTicker.innerHTML = "<span>No attendees yet</span>";
                return;
            }

            console.log("✅ Displaying attendees:", attendees);
            populateTicker(attendees);
        })
        .catch(error => {
            console.error("❌ Error fetching attendees:", error);
        });
    }


    function populateTicker(attendees) {
    attendeeTicker.innerHTML = ""; // Clear previous content

    attendees.forEach(name => {
        let attendeeElement = document.createElement("span");
        attendeeElement.textContent = name;
        attendeeElement.classList.add("ticker__item");
        attendeeTicker.appendChild(attendeeElement);
    });

    // Duplicate the list to create an infinite scroll effect
    attendees.forEach(name => {
        let cloneElement = document.createElement("span");
        cloneElement.textContent = name;
        cloneElement.classList.add("ticker__item");
        attendeeTicker.appendChild(cloneElement);
    });

    // ✅ Start animation if attendees exist
    if (attendeeTicker.children.length > 0) {
        startTickerAnimation();
    }
    }


    function startTickerAnimation() {
        attendeeTicker.style.animation = `tickerScroll 20s linear infinite`; // Smooth animation
    }

    fetchAttendees(); // ✅ Fetch attendees only if attendeeTicker exists

    function addAttendeeToTicker(name) {
        if (!attendeeTicker) {
            console.error("⚠️ attendeeTicker not found in the DOM.");
            return;
        }

        let attendeeElement = document.createElement("span");
        attendeeElement.textContent = name;
        attendeeElement.classList.add("ticker__item");

        attendeeTicker.appendChild(attendeeElement);

        // Ensure ticker animation starts if attendees exist
        if (attendeeTicker.children.length > 0) {
            startTickerAnimation();
        }
    }



    // General notification function
    function showNotification(message, type = "success", targetElement) {  // No default value
        if (targetElement) { // Check if targetElement exists
            targetElement.textContent = message;
            targetElement.className = `alert alert-${type}`;
            targetElement.style.display = "block";

            setTimeout(() => {
                targetElement.style.display = "none";
            }, 5000);
        } else {
            console.error("Notification target element not found!");
        }
    }

    function updatePagination() {
        // Get pagination element inside the function, after DOM is ready
        pagination = document.getElementById('pagination');

        if (!pagination) {
            console.error("Pagination element not found!");
            return; // Exit if the element is not found
        }

        const totalPages = Math.ceil(totalImages / imagesPerPage);
        pagination.innerHTML = ''; // Clear existing pagination links

        for (let i = 1; i <= totalPages; i++) {
            const li = document.createElement('li');
            li.className = 'page-item';
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = i;

            a.addEventListener('click', function (event) {
                event.preventDefault();
                currentPage = i;
                fetchGalleryImages(currentPage);
            });

            li.appendChild(a);
            pagination.appendChild(li);
        }
    }

    function updatePagination() {
            pagination = document.getElementById('pagination');

            if (!pagination) {
                console.error("Pagination element not found!");
                return;
            }

            const totalPages = Math.ceil(totalImages / imagesPerPage);
            pagination.innerHTML = '';

            for (let i = 1; i <= totalPages; i++) {
                const li = document.createElement('li');
                li.className = 'page-item';
                const a = document.createElement('a');
                a.className = 'page-link';
                a.href = '#';
                a.textContent = i;

                a.addEventListener('click', function (event) {
                    event.preventDefault();
                    currentPage = i;
                    fetchGalleryImages(currentPage);
                });

                li.appendChild(a);
                pagination.appendChild(li);
            }
    }

    function fetchGalleryImages(page = 1) {
        const offset = (page - 1) * imagesPerPage;

        console.log("Fetching images...");

        fetch(`/images?limit=${imagesPerPage}&offset=${offset}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("📸 Images fetched:", data);
                galleryGrid.innerHTML = "";

                if (!data.images || data.images.length === 0) {
                    console.log("📸 No images found in database.");
                    return;
                }

                if (data.images) {
                    data.images.forEach(image => {
                        const fullImageUrl = `${baseUrl}/uploads/${image.filename}`;

                        const col = document.createElement("div");
                        col.className = "col-md-3 mb-3";
                        col.innerHTML = `
                            <div class="card">
                                <img src="${fullImageUrl}" class="card-img-top img-thumbnail" onclick="openImageModal('${fullImageUrl}')" alt="Uploaded Image">
                            </div>
                        `;
                        galleryGrid.appendChild(col);
                    });
                }

                totalImages = data.total_images || 0;

                // Call updatePagination AFTER data is received AND DOM is ready
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', updatePagination);
                } else {
                    updatePagination();
                }

            })
            .catch(error => {
                console.error("❌ Error fetching images:", error);
                showNotification("Error fetching images. Please try again later.", "danger", galleryNotification);
            });
    }


    //    function openImageModal(imageUrl) {
    //        document.getElementById("modalImage").src = imageUrl;
    //        const imageModal = new bootstrap.Modal(document.getElementById("imageModal"));
    //        imageModal.show();
    //    }

//    function uploadImage() {
//        const file = uploadPhoto.files[0];
//        if (!file) {
//            showNotification("Please select an image to upload.", "danger", galleryNotification);
//            return;
//        }
//        const formData = new FormData();
//        formData.append("image", file);
//
//        fetch("/upload-image", {
//            method: "POST",
//            body: formData
//        })
//            .then(response => {
//                if (!response.ok) {
//                    throw new Error(`HTTP error! status: ${response.status}`);
//                }
//                return response.json();
//            })
//            .then(data => {
//                console.log("Upload response:", data);
//                if (data.success) {
//                    showNotification("Image uploaded successfully!", "success", galleryNotification);
//                    uploadPhoto.value = "";
//                    fetchGalleryImages();
//                } else {
//                    showNotification("Image upload failed: " + data.error, "danger", galleryNotification);
//                }
//            })
//            .catch(error => {
//                console.error("❌ Upload error:", error);
//                showNotification("An error occurred during upload. Please try again.", "danger", galleryNotification);
//            });
//    }

    function uploadImage() {
    const file = uploadPhoto.files[0];
    if (!file) {
        showNotification("Please select an image to upload.", "danger", galleryNotification);
        return;
    }

    const formData = new FormData();
    formData.append("image", file);

    fetch("/upload-image", {
        method: "POST",
        body: formData
    })
        .then(response => {
            if (!response.ok) {
                return response.text().then(err => {throw new Error(`HTTP error! status: ${response.status}, ${err}`);}); // Include error message from server
            }
            return response.json();
        })
        .then(data => {
            console.log("Upload response:", data);
            if (data.success) {
                showNotification("Image uploaded successfully!", "success", galleryNotification);
                uploadPhoto.value = "";
                fetchGalleryImages();
            } else {
                showNotification("Image upload failed: " + data.error, "danger", galleryNotification); // Display server error
            }
        })
        .catch(error => {
            console.error("❌ Upload error:", error);
            showNotification("An error occurred during upload. Please try again. " + error.message, "danger", galleryNotification); // Include error message
        });
    }


    fetchGalleryImages();
//    uploadPhoto.addEventListener("change", uploadImage); // Use addEventListener
    document.getElementById("uploadPhoto").addEventListener("change", uploadImage);


    // Registration/Payment functions
    function updateTotalCost() {
        totalCost = 0;
        document.querySelectorAll(".registrant").forEach(registrantDiv => {
            const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;
            const price = ageGroup === "adult" ? 125 : 50;
            totalCost += price;
        });
        totalCostSpan.textContent = `$${totalCost.toFixed(2)}`;
    }


    function updateCountdown() {
        const now = new Date();
        const distance = reunionDate.getTime() - now.getTime();

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        countdownTimer.innerHTML = `${days}d ${hours}h ${minutes}m ${seconds}s`;

        if (distance < 0) {
            clearInterval(countdownInterval);
            countdownTimer.innerHTML = "Reunion Time!";
        }
    }

    updateCountdown(); // Initial call to display countdown immediately
    const countdownInterval = setInterval(updateCountdown, 1000); // Update every second


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
        newRegistrantDiv.querySelector(".age-group-select").addEventListener("change", updateTotalCost);
        return newRegistrantDiv;
    }

    registrantFields.appendChild(createRegistrantBlock(registrantCount));
    updateTotalCost();

    addPersonButton.addEventListener("click", function () {
        registrantCount++;
        registrantFields.appendChild(createRegistrantBlock(registrantCount));
        updateTotalCost();
    });

    paymentButton.addEventListener("click", async (event) => {
        event.preventDefault();

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
                showNotification("Please enter all registrant names.", "danger", registrationNotification);
                return;
            }

            if (registrants.length === 0) {
                showNotification("Please add at least one registrant.", "danger", registrationNotification);
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

            console.log("✅ Checkout session created:", checkoutData);

            if (!checkoutResponse.ok || !checkoutData.sessionId ) { // Check for sessionId
                const errorMessage = checkoutData.error || "Invalid checkout session";
                console.error("❌ Error during checkout:", errorMessage);
                showNotification(errorMessage, "danger");
                throw new Error(errorMessage);
            }

            await stripe.redirectToCheckout({ sessionId: checkoutData.sessionId }); // Use stripe.redirectToCheckout

        } catch (error) {
            console.error("❌ Error during checkout:", error);
            showNotification("An error occurred during checkout. Please try again.", "danger");
        }
    });

    updateTotalCost();
});