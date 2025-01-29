document.addEventListener('DOMContentLoaded', function () {
    // Initialize Stripe (replace with your publishable key)
    const stripe = Stripe('pk_test_...');

    // Countdown Timer
    const targetDate = new Date('2025-07-17T00:00:00').getTime();

    const countdownInterval = setInterval(function () {
        const now = new Date().getTime();
        const distance = targetDate - now;

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        document.getElementById('countdown-timer').innerHTML = `
            ${days}d ${hours}h ${minutes}m ${seconds}s
        `;

        if (distance < 0) {
            clearInterval(countdownInterval);
            document.getElementById('countdown-timer').innerHTML = 'Reunion Time!';
        }
    }, 1000);

    // Add Person Button
    const addPersonButton = document.getElementById('addPerson');
    const registrantFields = document.getElementById('registrantFields');
    let registrantCount = 1;

    addPersonButton.addEventListener('click', function () {
        registrantCount++;

        const newRegistrantDiv = document.createElement('div');
        newRegistrantDiv.classList.add('registrant');
        newRegistrantDiv.innerHTML = `
            <div class="mb-3">
                <label for="name${registrantCount}" class="form-label">Name</label>
                <input type="text" class="form-control" id="name${registrantCount}" name="name" required>
            </div>
            <div class="mb-3">
                <label for="tshirtSize${registrantCount}" class="form-label">T-Shirt Size</label>
                <select class="form-select" id="tshirtSize${registrantCount}" name="tshirtSize">
                    <option value="S">S</option>
                    <option value="M">M</option>
                    <option value="L">L</option>
                    <option value="XL">XL</option>
                    <option value="XXL">XXL</option>
                </select>
            </div>
            <div class="mb-3">
                <label for="ageGroup${registrantCount}" class="form-label">Age Group</label>
                <select class="form-select" id="ageGroup${registrantCount}" name="ageGroup">
                    <option value="adult">Adult</option>
                    <option value="child">Child</option>
                </select>
            </div>
            <button type="button" class="btn btn-sm btn-danger remove-added-registrant float-end">Remove</button>
        `;

        registrantFields.appendChild(newRegistrantDiv);
    });

    // Event listener for removing dynamically added registrant fields
    registrantFields.addEventListener('click', function (event) {
        if (event.target.classList.contains('remove-added-registrant')) {
            const registrantDiv = event.target.closest('.registrant');
            registrantDiv.remove();
        }
    });

    // Registration Form Submission
    const registrationForm = document.getElementById('registrationForm');
    const paymentButton = document.getElementById('paymentButton');
    const registrantList = document.getElementById('registrantList');
    const totalCostSpan = document.getElementById('totalCost');
    let totalCost = 0;

    paymentButton.addEventListener('click', function () {
        let registrants = [];
        totalCost = 0; // Reset total cost
        registrantList.innerHTML = ''; // Clear the summary list

        const registrantDivs = document.querySelectorAll('.registrant');

        registrantDivs.forEach((registrantDiv) => {
            const name = registrantDiv.querySelector('[name="name"]').value;
            const tshirtSize = registrantDiv.querySelector('[name="tshirtSize"]').value;
            const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;

            let price;
            if (ageGroup === 'adult') {
                price = 50;
            } else {
                price = 25;
            }

            totalCost += price;

            registrants.push({
                name: name,
                tshirtSize: tshirtSize,
                ageGroup: ageGroup,
                price: price
            });

            // Add to summary list
            const listItem = document.createElement('li');
            listItem.classList.add('list-group-item');
            listItem.innerHTML = `
                ${name} - ${tshirtSize} - ${ageGroup} - $${price}
                <button type="button" class="btn btn-sm btn-danger float-end remove-registrant">Remove</button>
            `;
            registrantList.appendChild(listItem);
        });

        // Update total cost display
        totalCostSpan.textContent = totalCost.toFixed(2);

        // Send data to backend for validation and processing
        fetch('/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ registrants: registrants })
        })
        .then(response => response.json())
        .then(data => {
            if (data.message) {
                fetch('/create-checkout-session', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(session => {
                    return stripe.redirectToCheckout({ sessionId: session.id });
                })
                .then(result => {
                    if (result.error) {
                        alert(result.error.message);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error creating payment session.');
                });
            } else if (data.error) {
                alert(data.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error registering. Please try again.');
        });
    });

    // Remove Registrant from Summary
    registrantList.addEventListener('click', function (event) {
        if (event.target.classList.contains('remove-registrant')) {
            const listItem = event.target.closest('li');
            const priceString = listItem.textContent.split('- $')[1];
            const price = parseFloat(priceString);

            totalCost -= price;
            totalCostSpan.textContent = totalCost.toFixed(2);

            listItem.remove();
        }
    });

    // Volunteer Form Submission
    const volunteerForm = document.getElementById('volunteerForm');

    volunteerForm.addEventListener('submit', function (event) {
        event.preventDefault();

        const name = document.getElementById('volunteerName').value;
        const email = document.getElementById('volunteerEmail').value;

        fetch('/volunteer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `name=${name}&email=${email}`
        })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                // Reset the form and close the modal
                volunteerForm.reset();
                const volunteerModal = bootstrap.Modal.getInstance(document.getElementById('volunteerModal'));
                volunteerModal.hide();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error submitting form.');
            });
    });

    // Contact Form Submission
    const contactForm = document.getElementById('contactForm');

    contactForm.addEventListener('submit', function (event) {
        event.preventDefault();

        const name = document.getElementById('contactName').value;
        const email = document.getElementById('contactEmail').value;
        const message = document.getElementById('contactMessage').value;

        fetch('/contact', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `name=${name}&email=${email}&message=${message}`
        })
            .then(response => response.json())
            .then(data => {
                alert(data.message);
                // Reset the form
                contactForm.reset();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error submitting form.');
            });
    });

    // Function to upload image
    window.uploadImage = function() {
        const fileInput = document.getElementById('uploadPhoto');
        const file = fileInput.files[0];

        if (file) {
            const formData = new FormData();
            formData.append('file', file);

            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    alert(data.message);
                    addImageToGallery(data.url);
                } else {
                    alert(data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error uploading image.');
            });
        } else {
            alert('Please select a file to upload.');
        }
    }

    // Function to add an image to the gallery
    function addImageToGallery(imageUrl) {
        const galleryGrid = document.getElementById('galleryGrid');
        const newImageDiv = document.createElement('div');
        newImageDiv.className = 'col-md-4 mb-3';
        newImageDiv.innerHTML = `
            <div class="card gallery-card">
                <img src="${imageUrl}" class="card-img-top" alt="Uploaded Image">
            </div>
        `;
        galleryGrid.appendChild(newImageDiv);
    }
});