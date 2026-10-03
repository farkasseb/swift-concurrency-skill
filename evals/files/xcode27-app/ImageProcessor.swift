import UIKit

class ImageProcessor {
    func process(_ data: Data) async -> UIImage? {
        // Heavy decoding and resizing.
        UIImage(data: data)
    }
}
