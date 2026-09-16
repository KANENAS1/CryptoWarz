.PHONY: play test balance clean

play:      ## start a game
	python3 -m cryptowarz

test:      ## run the test suite
	python3 -m unittest discover -s tests -v

balance:   ## simulate strategies to check the game is still a game
	python3 scripts/balance.py

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
