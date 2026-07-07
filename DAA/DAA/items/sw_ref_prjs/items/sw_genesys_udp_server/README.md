# Ref project

This is a reference project for the Genesys ZU, based on the UDP server example from Vitis.

To use it, simply modify the source files, and the project should work as expected.

## Project Overview

This project sends multiple UDP frames, each containing 960 bytes, which are used to form an image. The client application receives these frames and appends 540 of them to reconstruct the image, which is then plotted in real time.

## Setup Instructions

- Modify the source files with this ones.
- Compile the project using Vitis.
- Run the server and client applications.
- The server will start sending UDP frames, and the client will reconstruct and display the image in real time
