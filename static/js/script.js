// Define openImageModal in the global scope (outside DOMContentLoaded)
function openImageModal(imageUrl) {
    document.getElementById("modalImage").src = imageUrl;
    const imageModal = new bootstrap.Modal(document.getElementById("imageModal"));
    imageModal.show();
}

// Global utility functions for comments and reactions
function promptForName() {
    const savedName = localStorage.getItem('familyUserName');
    if (savedName) return savedName;

    const name = prompt('Enter your name to comment/react:');
    if (name && name.trim()) {
        localStorage.setItem('familyUserName', name.trim());
        return name.trim();
    }
    return null;
}

function addReaction(itemType, itemId, reactionType, callback) {
    const name = promptForName();
    if (!name) return;

    fetch('/reactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            item_type: itemType,
            item_id: itemId,
            reactor_name: name,
            reaction_type: reactionType
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && callback) {
            callback();
        }
    })
    .catch(error => console.error('Error adding reaction:', error));
}

function loadReactions(itemType, itemId, containerElement) {
    fetch(`/reactions/${itemType}/${itemId}`)
        .then(response => response.json())
        .then(reactions => {
            const reactionIcons = {
                'love': '❤️',
                'like': '👍',
                'celebrate': '🎉',
                'haha': '😂',
                'wow': '😮'
            };

            let html = '<div class="reactions-display">';
            Object.keys(reactionIcons).forEach(type => {
                const count = reactions[type] || 0;
                const displayClass = count > 0 ? '' : 'opacity-50';
                html += `
                    <button class="btn btn-sm btn-light reaction-btn ${displayClass}"
                            onclick="addReaction('${itemType}', '${itemId}', '${type}', () => loadReactions('${itemType}', '${itemId}', document.getElementById('reactions-${itemType}-${itemId}')))"
                            title="${type.charAt(0).toUpperCase() + type.slice(1)}">
                        ${reactionIcons[type]} ${count > 0 ? count : ''}
                    </button>
                `;
            });
            html += '</div>';
            containerElement.innerHTML = html;
        })
        .catch(error => console.error('Error loading reactions:', error));
}

function loadComments(itemType, itemId, containerElement) {
    fetch(`/comments/${itemType}/${itemId}`)
        .then(response => response.json())
        .then(comments => {
            let html = '<div class="comments-list mt-2">';

            comments.forEach(comment => {
                const date = new Date(comment.created_at);
                const timeAgo = getTimeAgo(date);
                html += `
                    <div class="comment-item mb-2 p-2 bg-light rounded">
                        <div class="d-flex justify-content-between">
                            <strong>${comment.commenter_name}</strong>
                            <small class="text-muted">${timeAgo}</small>
                        </div>
                        <div>${comment.comment_text}</div>
                    </div>
                `;
            });

            html += '</div>';
            html += `
                <div class="add-comment mt-2">
                    <textarea class="form-control form-control-sm" placeholder="Write a comment..." rows="2" id="comment-text-${itemType}-${itemId}"></textarea>
                    <button class="btn btn-sm btn-primary mt-1" onclick="submitComment('${itemType}', '${itemId}')">Post Comment</button>
                </div>
            `;

            containerElement.innerHTML = html;
        })
        .catch(error => console.error('Error loading comments:', error));
}

function submitComment(itemType, itemId) {
    const name = promptForName();
    if (!name) return;

    const textArea = document.getElementById(`comment-text-${itemType}-${itemId}`);
    const commentText = textArea.value.trim();

    if (!commentText) {
        alert('Please enter a comment');
        return;
    }

    fetch('/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            item_type: itemType,
            item_id: itemId,
            commenter_name: name,
            comment_text: commentText
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            textArea.value = '';
            loadComments(itemType, itemId, document.getElementById(`comments-${itemType}-${itemId}`));
        }
    })
    .catch(error => console.error('Error submitting comment:', error));
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    const weeks = Math.floor(days / 7);
    if (weeks < 4) return `${weeks}w ago`;
    return date.toLocaleDateString();
}

document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ JavaScript Loaded...");

    // Check if attendeeTicker exists before trying to use it
    const attendeeTickerContainer = document.getElementById("attendeeTicker");
    const hasAttendeeTickerFeature = !!attendeeTickerContainer;

    // Only call fetchAttendees if the feature exists on the page
    if (hasAttendeeTickerFeature) {
        fetchAttendees();
    }

    // Gallery variables
    const galleryGrid = document.getElementById("galleryGrid");
    const uploadPhoto = document.getElementById("uploadPhoto");
    const galleryNotification = document.getElementById("galleryNotification");
    const uploadProgress = document.getElementById("uploadProgress");
    const uploadCount = document.getElementById("uploadCount");
    const uploadTotal = document.getElementById("uploadTotal");
    const baseUrl = window.location.origin;

    // Birthday and Event variables
    const birthdayForm = document.getElementById("birthdayForm");
    const birthdaysList = document.getElementById("birthdaysList");
    const eventForm = document.getElementById("eventForm");
    const eventsList = document.getElementById("eventsList");

    // Registration/Payment variables
    const stripe = Stripe("pk_live_51Qm6jDDeOdL1Uspnz81ANrY78bcjW5JeWMGd6uH92mgfsb3o6rHuPa4cZVql5y23KxIOUKcMr41ixK8a6kQ8n8uC00eq0uaMM3"); // Replace with your publishable key
    const addPersonButton = document.getElementById("addPerson");
    const registrantFields = document.getElementById("registrantFields");
    const totalCostSpan = document.getElementById("totalCost");
    const paymentButton = document.getElementById("paymentButton");
    const notification = document.getElementById("notification");

    // Countdown Timer Code:
    const countdownTimer = document.getElementById('countdown-timer');
    const reunionDate = new Date('2025-07-17T00:00:00'); // Set your reunion date and time

    // RSVP Form Handling
    const rsvpForm = document.getElementById('rsvpForm');
    const attendeeTicker = hasAttendeeTickerFeature ? attendeeTickerContainer.querySelector(".ticker") : null;

    //contact form:
    const contactForm = document.getElementById("contactForm");

    let registrantCount = 1;
    let totalCost = 0;
    let currentPage = 1;
    let imagesPerPage = 10;
    let totalImages = 0;
    let pagination;

    function addAttendeeToTicker(name) {
        // Skip if ticker feature isn't enabled on this page
        if (!hasAttendeeTickerFeature) return;

        const attendeeTickerContainer = document.getElementById("attendeeTicker");
        if (!attendeeTickerContainer) {
            console.error("⚠️ Error: #attendeeTicker not found in the DOM.");
            return;
        }

        let attendeeTicker = attendeeTickerContainer.querySelector(".ticker");
        if (!attendeeTicker) {
            console.warn("⚠️ .ticker element missing! Creating one...");
            attendeeTicker = document.createElement("div");
            attendeeTicker.classList.add("ticker");
            attendeeTickerContainer.appendChild(attendeeTicker);
        }

        let attendeeElement = document.createElement("span");
        attendeeElement.textContent = name;
        attendeeElement.classList.add("ticker__item");

        // Add the attendee's name to the ticker
        attendeeTicker.appendChild(attendeeElement);

        // ✅ Add separator **after** each name except the last one
        let separator = document.createElement("span");
        separator.textContent = " • ";
        separator.style.margin = "0 50px";
        separator.style.fontWeight = "bold";
        separator.style.color = "#dc3545";
        attendeeTicker.appendChild(separator);

        startTickerAnimation(); // Restart animation with the new attendee
    }

    if (contactForm) {
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
    }

    if (rsvpForm) {
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
                    console.log("✅ RSVP submitted successfully.");

                    // ✅ Only call addAttendeeToTicker if it exists
                    if (typeof addAttendeeToTicker === "function") {
                        addAttendeeToTicker(name);
                    } else {
                        console.error("⚠️ Error: addAttendeeToTicker function is not defined.");
                    }

                    rsvpForm.reset(); // Clear the form
                    alert("Thank you for your RSVP!");
                } else {
                    alert(data.error || "Error submitting RSVP. Please try again.");
                }
            })
            .catch(error => {
                console.error("❌ Error:", error);
                alert("An error occurred. Please try again later.");
            });
        });
    }

    function deleteItem(type, id) {
        if (confirm('Are you sure you want to delete this item?')) {
            fetch(`/delete_${type}/${id}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(data.message);
                    location.reload(); // Refresh the page to reflect changes
                } else {
                    alert('Error deleting item: ' + data.error);
                }
            })
            .catch(error => console.error('Error:', error));
        }
    }

    function fetchAttendees() {
        // Skip if ticker feature isn't enabled on this page
        if (!hasAttendeeTickerFeature) return;

        fetch('/attendees', { cache: 'no-store' })  // Ensure fresh data
            .then(response => response.json())
            .then(attendees => {
                console.log("✅ Fetching attendees from database:", attendees);

                const attendeeTickerContainer = document.getElementById("attendeeTicker");
                if (!attendeeTickerContainer) {
                    console.error("⚠️ Error: #attendeeTicker not found in the DOM.");
                    return;
                }

                let attendeeTicker = attendeeTickerContainer.querySelector(".ticker");
                if (!attendeeTicker) {
                    console.warn("⚠️ .ticker element missing! Creating one...");
                    attendeeTicker = document.createElement("div");
                    attendeeTicker.classList.add("ticker");
                    attendeeTickerContainer.appendChild(attendeeTicker);
                }

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
        // Skip if ticker feature isn't enabled on this page
        if (!hasAttendeeTickerFeature) return;

        const attendeeTickerContainer = document.getElementById("attendeeTicker");
        let attendeeTicker = attendeeTickerContainer.querySelector(".ticker");

        if (!attendeeTicker) {
            attendeeTicker = document.createElement("div");
            attendeeTicker.classList.add("ticker");
            attendeeTickerContainer.appendChild(attendeeTicker);
        }

        attendeeTicker.innerHTML = ""; // Clear previous content

        if (!attendees || attendees.length === 0) {
            attendeeTicker.innerHTML = "<span>No attendees yet</span>";
            return;
        }

        // ✅ Ensure all attendees are added once
        attendees.forEach((name, index) => {
            let attendeeElement = document.createElement("span");
            attendeeElement.textContent = name;
            attendeeElement.classList.add("ticker__item");
            attendeeTicker.appendChild(attendeeElement);

            // ✅ Add separator **after** each name except the last one
            if (index !== attendees.length - 1) {
                let separator = document.createElement("span");
                separator.textContent = " • ";
                separator.style.margin = "0 50px";
                separator.style.fontWeight = "bold";
                separator.style.color = "#dc3545";
                attendeeTicker.appendChild(separator);
            }
        });

        // ✅ Duplicate all attendees for continuous scrolling
        attendees.forEach((name, index) => {
            let cloneElement = document.createElement("span");
            cloneElement.textContent = name;
            cloneElement.classList.add("ticker__item");
            attendeeTicker.appendChild(cloneElement);

            // ✅ Add separator **after** every name except the last duplicate
            if (index !== attendees.length - 1) {
                let separator = document.createElement("span");
                separator.textContent = " • ";
                separator.style.margin = "0 50px";
                separator.style.fontWeight = "bold";
                separator.style.color = "#dc3545";
                attendeeTicker.appendChild(separator);
            }
        });

        startTickerAnimation(); // Ensure animation runs smoothly
    }

    // ✅ Move the style definition OUTSIDE the function to ensure it's added only once
    const style = document.createElement("style");
    style.innerHTML = `
        @keyframes tickerScroll {
            0% { transform: translateX(0%); }  /* Start immediately */
            100% { transform: translateX(-100%); }  /* Smooth scrolling */
        }
    `;
    document.head.appendChild(style);

    function startTickerAnimation() {
        // Skip if ticker feature isn't enabled on this page
        if (!hasAttendeeTickerFeature) return;

        const ticker = document.querySelector(".ticker");

        if (!ticker || ticker.children.length === 0) {
            console.error("⚠️ No attendees found for ticker animation.");
            return;
        }

        // ✅ Save original content before duplication
        const originalContent = Array.from(ticker.children).map(el => el.outerHTML).join("");

        // ✅ Clear & duplicate content for smooth scrolling
        ticker.innerHTML = originalContent + originalContent;  // Duplicate once

        // ✅ Ensure proper width
        const totalWidth = ticker.scrollWidth;
        ticker.style.width = `${totalWidth}px`;

        // ✅ Adjust speed dynamically (slower speed)
        const animationSpeed = Math.max(totalWidth / 50, 20);  // Adjusted to slow down
        ticker.style.animation = `tickerScroll ${animationSpeed}s linear infinite`;
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
            // Fallback: If targetElement doesn't exist, use alert
            alert(message);
        }
    }

    // pagination of the gallery function
    function updatePagination() {
        const pagination = document.getElementById('pagination');

        if (!pagination) {
            console.error("Pagination element not found!");
            return;
        }

        const totalPages = Math.ceil(totalImages / imagesPerPage);
        pagination.innerHTML = '';

        if (totalPages <= 1) return; // Hide pagination if only one page

        const maxVisiblePages = 5;  // Adjust this number as needed
        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

        // Add "Previous" button
        if (currentPage > 1) {
            const prevLi = document.createElement('li');
            prevLi.className = 'page-item';
            prevLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage - 1}">&laquo; Prev</a>`;
            pagination.appendChild(prevLi);
        }

        // Generate the page number links
        for (let i = startPage; i <= endPage; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === currentPage ? 'active' : ''}`;
            const a = document.createElement('a');
            a.className = 'page-link';
            a.href = '#';
            a.textContent = i;
            a.setAttribute('data-page', i);

            a.addEventListener('click', function (event) {
                event.preventDefault();
                currentPage = i;
                fetchGalleryImages(currentPage);
            });

            li.appendChild(a);
            pagination.appendChild(li);
        }

        // Add "Next" button
        if (currentPage < totalPages) {
            const nextLi = document.createElement('li');
            nextLi.className = 'page-item';
            nextLi.innerHTML = `<a class="page-link" href="#" data-page="${currentPage + 1}">Next &raquo;</a>`;
            pagination.appendChild(nextLi);
        }

        // Ensure the pagination container is scrollable
        pagination.parentElement.classList.add('pagination-container');

        // Add event listeners for "Next" and "Previous" buttons
        pagination.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', function(event) {
                event.preventDefault();
                currentPage = parseInt(this.getAttribute('data-page'));
                fetchGalleryImages(currentPage);
            });
        });
    }

    function fetchGalleryImages(page = 1) {
        // Skip if gallery feature isn't available
        if (!galleryGrid) return;

        const offset = (page - 1) * imagesPerPage;
        console.log(`📸 Fetching images from server... Page: ${page}, Offset: ${offset}`);

        fetch(`/images?limit=${imagesPerPage}&offset=${offset}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("📸 Images fetched:", data);
                galleryGrid.innerHTML = ""; // Clear old images before adding new ones

                if (!data.images || data.images.length === 0) {
                    console.log("⚠️ No images found.");
                    galleryGrid.innerHTML = "<p>No images uploaded yet.</p>";
                    return;
                }

                data.images.forEach(item => {
                    const fullFileUrl = `${window.location.origin}/uploads/${item.filename}`;
                    const col = document.createElement("div");
                    col.className = "col-md-3 mb-3";

                    if (item.is_video) {
                        // Display video with proper MIME type
                        let mimeType = 'video/mp4';
                        if (item.type === 'mov') {
                            mimeType = 'video/quicktime';
                        } else if (item.type === 'webm') {
                            mimeType = 'video/webm';
                        } else if (item.type === 'avi') {
                            mimeType = 'video/x-msvideo';
                        }

                        col.innerHTML = `
                            <div class="card gallery-card">
                                <video class="card-img-top" controls preload="metadata" playsinline style="width: 100%; height: 200px; object-fit: cover; background: #000;">
                                    <source src="${fullFileUrl}" type="${mimeType}">
                                    Your browser does not support this video format.
                                </video>
                                <div class="card-body text-center p-2">
                                    <small class="text-muted d-block">${item.type.toUpperCase()} video</small>
                                    <a href="${fullFileUrl}" download class="btn btn-sm btn-outline-primary mt-1">
                                        <small>Download</small>
                                    </a>
                                </div>
                            </div>
                        `;
                    } else {
                        // Display image
                        col.innerHTML = `
                            <div class="card gallery-card">
                                <img src="${fullFileUrl}" class="card-img-top img-thumbnail gallery-img" onclick="openImageModal('${fullFileUrl}')" alt="Uploaded Image">
                                <div class="card-body p-2">
                                    <div class="border-top pt-2">
                                        <div id="reactions-photo-${item.filename}" class="mb-2"></div>
                                        <details class="mt-2">
                                            <summary class="text-primary small" style="cursor: pointer;">💬 Comments</summary>
                                            <div id="comments-photo-${item.filename}" class="mt-2"></div>
                                        </details>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    galleryGrid.appendChild(col);

                    // Load reactions and comments for this photo
                    if (!item.is_video) {
                        const reactionsContainer = document.getElementById(`reactions-photo-${item.filename}`);
                        if (reactionsContainer) {
                            loadReactions('photo', item.filename, reactionsContainer);
                        }

                        // Load comments when details are opened
                        const detailsElement = col.querySelector('details');
                        if (detailsElement) {
                            detailsElement.addEventListener('toggle', function() {
                                if (this.open) {
                                    const commentsContainer = document.getElementById(`comments-photo-${item.filename}`);
                                    if (commentsContainer && !commentsContainer.dataset.loaded) {
                                        loadComments('photo', item.filename, commentsContainer);
                                        commentsContainer.dataset.loaded = 'true';
                                    }
                                }
                            });
                        }
                    }
                });

                totalImages = data.total_images || 0;
                updatePagination();
            })
            .catch(error => {
                console.error("❌ Error fetching images:", error);
                if (galleryNotification) {
                    galleryNotification.innerHTML = "<p style='color: red;'>Error loading images. Please try again later.</p>";
                    galleryNotification.style.display = "block";
                }
            });
    }

    async function uploadImage() {
        const files = uploadPhoto.files;
        if (!files || files.length === 0) {
            showNotification("Please select files to upload.", "danger", galleryNotification);
            return;
        }

        console.log(`📤 Starting upload of ${files.length} file(s)`);

        // Show progress bar
        if (uploadProgress) {
            uploadProgress.style.display = "block";
            uploadTotal.textContent = files.length;
            uploadCount.textContent = "0";
        }

        let successCount = 0;
        let failCount = 0;
        let errorMessages = [];

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            console.log(`📎 Uploading file ${i + 1}/${files.length}: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);

            const formData = new FormData();
            formData.append("image", file);

            try {
                const response = await fetch("/upload-image", {
                    method: "POST",
                    body: formData
                });

                console.log(`📡 Response status: ${response.status} for ${file.name}`);

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`❌ Upload failed for ${file.name}:`, errorText);
                    throw new Error(`HTTP error! status: ${response.status}, ${errorText}`);
                }

                const data = await response.json();
                if (data.success) {
                    console.log(`✅ Successfully uploaded: ${file.name}`);
                    successCount++;
                } else {
                    console.error(`❌ Server reported failure for ${file.name}:`, data.error);
                    errorMessages.push(`${file.name}: ${data.error || 'Unknown error'}`);
                    failCount++;
                }
            } catch (error) {
                console.error(`❌ Upload error for ${file.name}:`, error);
                errorMessages.push(`${file.name}: ${error.message}`);
                failCount++;
            }

            // Update progress
            const uploadedSoFar = i + 1;
            if (uploadCount) uploadCount.textContent = uploadedSoFar;
            if (uploadProgress) {
                const progressBar = uploadProgress.querySelector(".progress-bar");
                const percentage = (uploadedSoFar / files.length) * 100;
                progressBar.style.width = percentage + "%";
            }
        }

        // Hide progress bar after a delay
        setTimeout(() => {
            if (uploadProgress) uploadProgress.style.display = "none";
        }, 2000);

        // Show summary notification
        let message = "";
        if (successCount > 0) {
            message += `${successCount} file(s) uploaded successfully! `;
        }
        if (failCount > 0) {
            message += `${failCount} file(s) failed to upload.`;
            if (errorMessages.length > 0) {
                console.error("Upload errors:", errorMessages);
                // Show first error in notification
                message += ` Error: ${errorMessages[0]}`;
            }
        }

        console.log(`📊 Upload complete: ${successCount} success, ${failCount} failed`);
        showNotification(message, failCount > 0 ? "warning" : "success", galleryNotification);
        uploadPhoto.value = "";
        fetchGalleryImages();
    }

    // Functions for registration
    function createRegistrantBlock(count) {
        const newRegistrantDiv = document.createElement("div");
        newRegistrantDiv.classList.add("registrant", "border", "p-3", "mb-3");
        newRegistrantDiv.dataset.id = count; // Store the ID for easy reference

        newRegistrantDiv.innerHTML = `
            <div class="d-flex justify-content-between align-items-start mb-2">
                <h5>Registrant #${count}</h5>
                ${count > 1 ? '<button type="button" class="btn btn-sm btn-danger remove-registrant">Remove</button>' : ''}
            </div>
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
                    <option value="adult">Adult ($75)</option>
                    <option value="child">Child ($25)</option>
                </select>
            </div>
        `;

        // Add event listener for the age group to update total cost
        newRegistrantDiv.querySelector(".age-group-select").addEventListener("change", updateTotalCost);

        // Add event listener for the remove button (if it exists)
        const removeButton = newRegistrantDiv.querySelector('.remove-registrant');
        if (removeButton) {
            removeButton.addEventListener('click', function() {
                newRegistrantDiv.remove();
                updateTotalCost();
                updateRegistrantNumbers();
            });
        }

        return newRegistrantDiv;
    }

    // Function to update the registrant numbers after removal
    function updateRegistrantNumbers() {
        const registrants = document.querySelectorAll('.registrant');
        registrants.forEach((registrant, index) => {
            const headingEl = registrant.querySelector('h5');
            if (headingEl) {
                headingEl.textContent = `Registrant #${index + 1}`;
            }
        });
    }

    // Update the total cost function
    function updateTotalCost() {
        totalCost = 0;
        document.querySelectorAll(".registrant").forEach(registrantDiv => {
            const ageGroup = registrantDiv.querySelector('[name="ageGroup"]').value;
            const price = ageGroup === "adult" ? 75 : 25;  // Updated prices
            totalCost += price;
        });
        if (totalCostSpan) {
            totalCostSpan.textContent = totalCost.toFixed(2);
        }
    }

    // Initialize with one registrant if the registration form exists
    if (registrantFields) {
        registrantFields.appendChild(createRegistrantBlock(registrantCount));
        updateTotalCost();

        // Set up add person button
        if (addPersonButton) {
            addPersonButton.addEventListener("click", function () {
                registrantCount++;
                registrantFields.appendChild(createRegistrantBlock(registrantCount));
                updateTotalCost();
            });
        }
    }

    // Set up payment button functionality
    if (paymentButton) {
        paymentButton.addEventListener("click", async (event) => {
            event.preventDefault();

            // Disable the button to prevent double-clicks
            paymentButton.disabled = true;
            paymentButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';

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

                    registrants.push({ name, tshirtSize, ageGroup });
                });

                if (!allRegistrantsValid) {
                    showNotification("Please enter all registrant names.", "danger", notification);
                    paymentButton.disabled = false;
                    paymentButton.innerHTML = 'Proceed to Payment';
                    return;
                }

                if (registrants.length === 0) {
                    showNotification("Please add at least one registrant.", "danger", notification);
                    paymentButton.disabled = false;
                    paymentButton.innerHTML = 'Proceed to Payment';
                    return;
                }

                console.log("📌 Sending registration data:", registrants);

                // Step 1: Register participants
                const registerResponse = await fetch("/register", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ registrants })
                });

                if (!registerResponse.ok) {
                    const registerData = await registerResponse.json();
                    throw new Error(registerData.error || "Registration failed");
                }

                const registerData = await registerResponse.json();
                console.log("✅ Registration successful:", registerData);

                // Show a success message for registration
                showNotification("Registration successful! Processing payment...", "success", notification);

                // Step 2: Create checkout session (no need to send registrants again, the server will use the session)
                const checkoutResponse = await fetch("/create-checkout-session", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });

                if (!checkoutResponse.ok) {
                    const checkoutData = await checkoutResponse.json();
                    throw new Error(checkoutData.error || "Checkout session creation failed");
                }

                const checkoutData = await checkoutResponse.json();
                console.log("✅ Checkout session created:", checkoutData);

                if (!checkoutData.sessionId) {
                    throw new Error("Invalid checkout session: No session ID returned");
                }

                // Redirect to Stripe checkout place
                const result = await stripe.redirectToCheckout({ sessionId: checkoutData.sessionId });

                if (result.error) {
                    throw new Error(result.error.message);
                }

            } catch (error) {
                console.error("❌ Error during registration/checkout:", error);
                showNotification("Error: " + error.message, "danger", notification);

                // Re-enable the button on error
                paymentButton.disabled = false;
                paymentButton.innerHTML = 'Proceed to Payment';
            }
        });
    }

    let countdownInterval; // Declare at top level to avoid scoping issues

    function updateCountdown() {
        if (!countdownTimer) return;

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

    // Initialize countdown timer if it exists
    if (countdownTimer) {
        updateCountdown(); // Initial call to display countdown immediately
        countdownInterval = setInterval(updateCountdown, 1000); // Update every second
    }

    // Initialize the page features based on what's available
    if (galleryGrid) {
        fetchGalleryImages();
    }

    // Set up the upload photo event listener
    if (uploadPhoto) {
        uploadPhoto.addEventListener("change", uploadImage);
    }

    // Birthday Functions
    function fetchBirthdays() {
        if (!birthdaysList) return;

        fetch('/birthdays')
            .then(response => response.json())
            .then(birthdays => {
                birthdaysList.innerHTML = '';
                if (birthdays.length === 0) {
                    birthdaysList.innerHTML = '<p class="text-muted">No birthdays added yet.</p>';
                    return;
                }

                const currentMonth = new Date().getMonth();
                const currentYear = new Date().getFullYear();

                // Helper function to check if birthday is a milestone
                function isMilestoneBirthday(birthYear, birthdayDate) {
                    if (!birthYear) return false;

                    const age = currentYear - birthYear;
                    const milestones = [13, 16, 18, 21];

                    // Check if age is milestone (13, 16, 18, 21, or ends in 0 or 5)
                    if (milestones.includes(age)) return true;
                    if (age % 10 === 0 || age % 10 === 5) return true;

                    return false;
                }

                // Group birthdays by month
                const monthGroups = {};
                const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                                   'July', 'August', 'September', 'October', 'November', 'December'];

                birthdays.forEach(birthday => {
                    const date = new Date(birthday.birth_date + 'T00:00:00');
                    const month = date.getMonth(); // 0-11
                    const day = date.getDate();
                    const age = birthday.birth_year ? currentYear - birthday.birth_year : null;

                    if (!monthGroups[month]) {
                        monthGroups[month] = [];
                    }
                    monthGroups[month].push({
                        name: birthday.name,
                        day: day,
                        date: date,
                        birthYear: birthday.birth_year,
                        age: age,
                        isMilestone: isMilestoneBirthday(birthday.birth_year, date)
                    });
                });

                // Sort birthdays within each month by day
                Object.keys(monthGroups).forEach(month => {
                    monthGroups[month].sort((a, b) => a.day - b.day);
                });

                // Create month cards in chronological order
                Object.keys(monthGroups).sort((a, b) => parseInt(a) - parseInt(b)).forEach(monthIndex => {
                    const monthName = monthNames[monthIndex];
                    const birthdaysInMonth = monthGroups[monthIndex];
                    const isCurrentMonth = parseInt(monthIndex) === currentMonth;

                    const monthCard = document.createElement('div');
                    monthCard.className = 'card mb-3';

                    // Highlight current month card
                    const headerClass = isCurrentMonth ? 'bg-warning text-dark' : 'bg-primary text-white';
                    const currentMonthBadge = isCurrentMonth ? '<span class="badge bg-dark ms-2">This Month!</span>' : '';

                    monthCard.innerHTML = `
                        <div class="card-header ${headerClass}">
                            <h5 class="mb-0">${monthName}${currentMonthBadge}</h5>
                        </div>
                        <div class="card-body">
                            <div class="row g-2"></div>
                        </div>
                    `;

                    const row = monthCard.querySelector('.row');
                    birthdaysInMonth.forEach(birthday => {
                        const col = document.createElement('div');
                        col.className = 'col-md-4 col-sm-6';

                        // Build the birthday item with milestone indicators
                        let milestoneIndicator = '';
                        let itemClass = 'birthday-item p-2 border rounded';

                        if (birthday.isMilestone) {
                            milestoneIndicator = `<span class="milestone-badge">🎉</span>`;
                            itemClass += ' milestone-birthday';
                        }

                        col.innerHTML = `
                            <div class="${itemClass}">
                                <div class="d-flex align-items-center justify-content-between">
                                    <div class="d-flex align-items-center">
                                        <div class="birthday-day me-2">
                                            <span class="badge bg-secondary" style="font-size: 1rem;">${birthday.day}</span>
                                        </div>
                                        <div class="birthday-name">
                                            <strong>${birthday.name}</strong>
                                        </div>
                                    </div>
                                    ${milestoneIndicator}
                                </div>
                            </div>
                        `;
                        row.appendChild(col);
                    });

                    birthdaysList.appendChild(monthCard);
                });
            })
            .catch(error => console.error('Error fetching birthdays:', error));
    }

    if (birthdayForm) {
        birthdayForm.addEventListener('submit', function(event) {
            event.preventDefault();

            const name = document.getElementById('birthdayName').value;
            const date = document.getElementById('birthdayDate').value;

            // Extract year from the date if provided (format: YYYY-MM-DD)
            const payload = { name, date };
            if (date && date.length === 10) {
                const year = parseInt(date.split('-')[0]);
                // Only include birth_year if it's a reasonable year (not just month/day)
                if (year >= 1900 && year <= new Date().getFullYear()) {
                    payload.birth_year = year;
                }
            }

            fetch('/birthdays', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Birthday added successfully!');
                    birthdayForm.reset();
                    fetchBirthdays();
                    // Collapse the form after successful submission
                    const collapseElement = document.getElementById('addBirthdayForm');
                    if (collapseElement) {
                        const bsCollapse = bootstrap.Collapse.getInstance(collapseElement);
                        if (bsCollapse) {
                            bsCollapse.hide();
                        }
                    }
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    }

    // Event Functions
    let allEvents = [];
    let currentEventView = 'upcoming';
    let currentMonthFilter = 'all';

    function fetchEvents() {
        if (!eventsList) return;

        fetch('/events')
            .then(response => response.json())
            .then(events => {
                allEvents = events;
                displayFilteredEvents();
                populateEventImageSelect();
            })
            .catch(error => console.error('Error fetching events:', error));
    }

    function displayFilteredEvents() {
        if (!eventsList) return;

        eventsList.innerHTML = '';
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // Filter events
        let filteredEvents = allEvents.filter(event => {
            const eventDate = new Date(event.event_date + 'T00:00:00');
            const eventMonth = eventDate.getMonth();

            // Filter by view (upcoming/past/all)
            if (currentEventView === 'upcoming' && eventDate < today) return false;
            if (currentEventView === 'past' && eventDate >= today) return false;

            // Filter by month
            if (currentMonthFilter !== 'all' && eventMonth !== parseInt(currentMonthFilter)) return false;

            return true;
        });

        // Sort events (upcoming: soonest first, past: most recent first)
        filteredEvents.sort((a, b) => {
            const dateA = new Date(a.event_date + 'T00:00:00');
            const dateB = new Date(b.event_date + 'T00:00:00');
            return currentEventView === 'past' ? dateB - dateA : dateA - dateB;
        });

        if (filteredEvents.length === 0) {
            eventsList.innerHTML = '<p class="text-muted">No events found for this selection.</p>';
            return;
        }

        filteredEvents.forEach(event => {
            const eventDate = new Date(event.event_date + 'T00:00:00');
            const formattedDate = eventDate.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });

            const isPast = eventDate < today;

            const card = document.createElement('div');
            card.className = `card mb-3 ${isPast ? 'opacity-75' : ''}`;

            let imageHtml = '';
            if (event.image_url) {
                imageHtml = `<img src="${event.image_url}" class="card-img-top" style="max-height: 300px; object-fit: cover;" alt="${event.title}">`;
            }

            card.innerHTML = `
                ${imageHtml}
                <div class="card-body">
                    <h5 class="card-title">${event.title} ${isPast ? '<span class="badge bg-secondary">Past</span>' : ''}</h5>
                    <h6 class="card-subtitle mb-2 text-muted">📅 ${formattedDate}</h6>
                    <p class="card-text">${event.description}</p>

                    <div class="border-top mt-3 pt-2">
                        <div id="reactions-event-${event.id}" class="mb-2"></div>
                        <details class="mt-2">
                            <summary class="text-primary" style="cursor: pointer;">💬 Comments</summary>
                            <div id="comments-event-${event.id}" class="mt-2"></div>
                        </details>
                    </div>
                </div>
            `;
            eventsList.appendChild(card);

            // Load reactions and comments
            loadReactions('event', event.id.toString(), document.getElementById(`reactions-event-${event.id}`));
            const commentsContainer = document.getElementById(`comments-event-${event.id}`);
            commentsContainer.addEventListener('toggle', function(e) {
                if (e.target.open) {
                    loadComments('event', event.id.toString(), commentsContainer);
                }
            }, { once: true });
        });
    }

    function populateEventImageSelect() {
        const imageSelect = document.getElementById('eventImageSelect');
        if (!imageSelect) return;

        // Keep the "No image" option
        imageSelect.innerHTML = '<option value="">-- No image --</option>';

        // Fetch uploaded images
        fetch('/images?limit=1000')
            .then(response => response.json())
            .then(data => {
                if (data.images && data.images.length > 0) {
                    // Only show actual images (not videos)
                    data.images.filter(img => !img.is_video).forEach(img => {
                        const option = document.createElement('option');
                        option.value = `/uploads/${img.filename}`;
                        option.textContent = img.filename;
                        imageSelect.appendChild(option);
                    });
                }
            })
            .catch(error => console.error('Error loading images:', error));
    }

    // Event filters
    const eventMonthFilter = document.getElementById('eventMonthFilter');
    if (eventMonthFilter) {
        eventMonthFilter.addEventListener('change', function() {
            currentMonthFilter = this.value;
            displayFilteredEvents();
        });
    }

    const eventViewRadios = document.querySelectorAll('input[name="eventView"]');
    eventViewRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            currentEventView = this.value;
            displayFilteredEvents();
        });
    });

    if (eventForm) {
        eventForm.addEventListener('submit', function(event) {
            event.preventDefault();

            const title = document.getElementById('eventTitle').value;
            const date = document.getElementById('eventDate').value;
            const description = document.getElementById('eventDescription').value;
            const imageUrl = document.getElementById('eventImageSelect').value;

            const payload = { title, date, description };
            if (imageUrl) {
                payload.image_url = imageUrl;
            }

            fetch('/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Event added successfully!');
                    eventForm.reset();
                    fetchEvents();
                    // Collapse the form after successful submission
                    const collapseElement = document.getElementById('addEventForm');
                    if (collapseElement) {
                        const bsCollapse = bootstrap.Collapse.getInstance(collapseElement);
                        if (bsCollapse) {
                            bsCollapse.hide();
                        }
                    }
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    }

    // Initialize birthday and event sections
    if (birthdaysList) fetchBirthdays();
    if (eventsList) fetchEvents();

});


