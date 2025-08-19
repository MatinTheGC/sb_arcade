document.addEventListener("DOMContentLoaded", () => {
  const gameListElement = document.getElementById("game-list");
  const searchInput = document.getElementById("search-input");
  const noResultsElement = document.getElementById("no-results");
  const faqQuestions = document.querySelectorAll(".faq-question");

  let allGames = []; // To store the master list of games

  /**
   * Fetches the list of games from a JSON file and populates the list.
   */
  async function fetchAndDisplayGames() {
    try {
      // We'll create this games.json file in the next step.
      // It will contain a list of all games with their slugs and friendly names.
      const response = await fetch("games.json");
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      allGames = await response.json();

      // Sort games alphabetically by friendly name
      allGames.sort((a, b) => a.name.localeCompare(b.name));

      displayGames(allGames);
    } catch (error) {
      console.error("Could not fetch or process game list:", error);
      gameListElement.innerHTML =
        '<li><a href="#">Error loading game list. Please try refreshing.</a></li>';
    }
  }

  /**
   * Renders a list of games to the DOM.
   * @param {Array<Object>} games - An array of game objects {slug, name}.
   */
  function displayGames(games) {
    gameListElement.innerHTML = ""; // Clear existing list

    if (games.length === 0) {
      noResultsElement.style.display = "block";
    } else {
      noResultsElement.style.display = "none";
    }

    games.forEach((game) => {
      const listItem = document.createElement("li");
      const link = document.createElement("a");

      // The link points to the index.html inside the game's folder.
      link.href = `games/${game.slug}`;
      link.textContent = game.name;
      link.target = "_blank"; // Open games in a new tab

      listItem.appendChild(link);
      gameListElement.appendChild(listItem);
    });
  }

  /**
   * Handles the search input to filter the displayed games.
   */
  function handleSearch() {
    const searchTerm = searchInput.value.toLowerCase().trim();
    const filteredGames = allGames.filter((game) =>
      game.name.toLowerCase().includes(searchTerm),
    );
    displayGames(filteredGames);
  }

  /**
   * Sets up the FAQ accordion functionality.
   */
  function setupFAQ() {
    faqQuestions.forEach((question) => {
      question.addEventListener("click", () => {
        const answer = question.nextElementSibling;
        const isActive = question.classList.contains("active");

        // Optional: Close other open FAQs
        faqQuestions.forEach((q) => {
          q.classList.remove("active");
          q.nextElementSibling.style.maxHeight = null;
          q.nextElementSibling.style.padding = "0 20px"; // Reset padding
        });

        if (!isActive) {
          question.classList.add("active");
          answer.style.maxHeight = answer.scrollHeight + 40 + "px"; // Add padding height
          answer.style.padding = "20px";
        }
      });
    });
  }

  // --- Initial Setup ---
  fetchAndDisplayGames();
  searchInput.addEventListener("input", handleSearch);
  setupFAQ();
});
