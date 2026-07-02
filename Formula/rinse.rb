class Rinse < Formula
  desc "Clean messy CSV and Excel files with auditable reports"
  homepage "https://github.com/Hqzdev/Rinse"
  license "MIT"
  head "https://github.com/Hqzdev/Rinse.git", branch: "main"

  depends_on "python@3.11"

  def install
    system "python3.11", "-m", "venv", libexec
    system libexec/"bin/pip", "install", "."
    bin.install_symlink libexec/"bin/rinse"
  end

  test do
    system "#{bin}/rinse", "--help"
  end
end
