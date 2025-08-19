// Wait for the page to be completely loaded
window.addEventListener('load', function() {
  console.log("Page fully loaded, initializing chat...");
  
  // Get all required elements
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const chatMessages = document.getElementById("chatMessages");
  
  console.log("Elements found:", {
    form: chatForm,
    input: userInput,
    messages: chatMessages
  });
  
  // Verify all elements exist
  if (!chatForm || !userInput || !chatMessages) {
    console.error("❌ Missing required elements:", {
      form: !!chatForm,
      input: !!userInput,
      messages: !!chatMessages
    });
    return;
  }
  
  console.log("✅ All elements found, setting up event listeners");
  
  // Set up form submission handler
  chatForm.addEventListener("submit", function(e) {
    e.preventDefault();
    console.log("Form submitted");
    
    // Get the message
    const message = userInput.value.trim();
    if (!message) {
      console.log("Empty message, ignoring");
      return;
    }
    
    console.log("Processing message:", message);
    
    // Display user message
    const userMsg = document.createElement("div");
    userMsg.className = "user-message message";
    userMsg.textContent = message;
    chatMessages.appendChild(userMsg);
    
    // Clear input
    userInput.value = "";
    
    // Send to server
    sendToServer(message);
  });
  
  console.log("✅ Chat functionality initialized successfully");
});

// Function to send message to server
async function sendToServer(message) {
  try {
    console.log("Sending to server:", message);
    
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ message: message })
    });
    
    console.log("Response status:", response.status);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    console.log("Server response:", data);
    
    // Display bot response
    const botMsg = document.createElement("div");
    botMsg.className = "bot-message message";
    
    if (data.error) {
      botMsg.textContent = `Error: ${data.error}`;
      botMsg.classList.add("error-message");
    } else if (data.response) {
      botMsg.textContent = data.response;
    } else {
      botMsg.textContent = "No response from server";
      botMsg.classList.add("error-message");
    }
    
    document.getElementById("chatMessages").appendChild(botMsg);
    
  } catch (error) {
    console.error("Error:", error);
    
    // Display error message
    const errorMsg = document.createElement("div");
    errorMsg.className = "bot-message message error-message";
    errorMsg.textContent = `Error: ${error.message}`;
    document.getElementById("chatMessages").appendChild(errorMsg);
  }
}
