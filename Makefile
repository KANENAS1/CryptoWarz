.PHONY: play test balance web web-balance clean

play:        ## start a game in the terminal
	python3 -m cryptowarz

test:        ## run the test suite
	python3 -m unittest discover -s tests -v

balance:     ## simulate strategies to check the game is still a game
	python3 scripts/balance.py

web:         ## flatten web/ into one file for publishing
	python3 web/build.py

web-balance: ## run the balance table against the JS port (needs node)
	node web/balance.js 200

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	rm -f web/cryptowarz.artifact.html
