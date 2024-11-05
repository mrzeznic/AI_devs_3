import unittest
from unittest.mock import patch, MagicMock
from W1_L02_robot import (
    initialize_openai_api,
    start_verification,
    answer_with_openai,
    construct_answer,
    send_answer
)

class TestRobotVerification(unittest.TestCase):

    @patch("W1_L02_robot.requests.post")
    def test_start_verification_successful(self, mock_post):
        """Test successful start of verification process with a mock response."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"text": "What is the capital of Poland?", "msgID": "12345"}

        response = start_verification()
        self.assertIsNotNone(response)
        self.assertEqual(response["text"], "What is the capital of Poland?")
        self.assertEqual(response["msgID"], "12345")

    @patch("W1_L02_robot.requests.post")
    def test_start_verification_failure(self, mock_post):
        """Test failed start of verification with an HTTP error."""
        mock_post.side_effect = requests.RequestException("Network error")
        response = start_verification()
        self.assertIsNone(response)

    @patch("W1_L02_robot.openai.ChatCompletion.create")
    def test_answer_with_openai_successful(self, mock_openai_create):
        """Test OpenAI API generates an answer in English regardless of prompt language."""
        mock_openai_create.return_value = {
            "choices": [{"message": {"content": "The capital of Poland is Warsaw"}}]
        }

        question = "What is the capital of Poland?"
        answer = answer_with_openai(question)
        self.assertEqual(answer, "The capital of Poland is Warsaw")

    @patch("W1_L02_robot.openai.ChatCompletion.create")
    def test_answer_with_openai_failure(self, mock_openai_create):
        """Test OpenAI API error handling."""
        mock_openai_create.side_effect = Exception("API error")
        question = "What is 2 + 2?"
        answer = answer_with_openai(question)
        self.assertEqual(answer, "I am unable to provide that information.")

    def test_construct_answer_incorrect_answer(self):
        """Test that predefined incorrect answers are returned when applicable."""
        question = "What is the capital of Poland?"
        answer = construct_answer(question, msg_id="12345")
        self.assertEqual(answer, {"text": "Kraków", "msgID": "12345"})

    @patch("W1_L02_robot.answer_with_openai")
    def test_construct_answer_openai_answer(self, mock_answer_with_openai):
        """Test that OpenAI provides an answer when no incorrect answer is predefined."""
        mock_answer_with_openai.return_value = "4"
        question = "What is 2 + 2?"
        answer = construct_answer(question, msg_id="67890")
        self.assertEqual(answer, {"text": "4", "msgID": "67890"})

    @patch("W1_L02_robot.requests.post")
    def test_send_answer_successful(self, mock_post):
        """Test successful sending of an answer."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.text = "Verification successful"

        answer = {"text": "4", "msgID": "67890"}
        send_answer(answer)
        mock_post.assert_called_once_with(VERIFY_URL, json=answer)

    @patch("W1_L02_robot.requests.post")
    def test_send_answer_failure(self, mock_post):
        """Test sending answer when there's a network error."""
        mock_post.side_effect = requests.RequestException("Network error")

        answer = {"text": "4", "msgID": "67890"}
        with self.assertLogs(level="INFO") as log:
            send_answer(answer)
            self.assertIn("Error sending answer", log.output[0])

if __name__ == "__main__":
    unittest.main()