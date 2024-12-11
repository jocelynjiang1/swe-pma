document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".accept, .reject").forEach((button) => {
    button.addEventListener("click", function () {
      const requestID = this.getAttribute("data-id");
      const newStatus = this.getAttribute("data-status");
      console.log(
        `Sending request to: /answer_request/${requestID}/ with status: ${newStatus}`,
      );

      fetch(`/answer_request/${requestID}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          new_status: newStatus,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.success) {
            // select join request in DOM and remove it
            const requestElement = document.getElementById(
              `pending_join_request-${requestID}`,
            );
            if (requestElement) {
              requestElement.remove();
            }
          } else {
            alert(data.error || "Error processing data.");
          }
        })
        // catch error
        .catch((error) => {
          console.error("Error:", error);
          alert("Something went wrong.");
        });
    });
  });
});

// CSRF Token Helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split("; ");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i];
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.split("=")[1]);
        break;
      }
    }
  }
  return cookieValue;
}