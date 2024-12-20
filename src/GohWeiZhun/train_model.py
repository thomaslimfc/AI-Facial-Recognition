import os
import tensorflow as tf
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D
from tensorflow.keras.optimizers import Adam


# Define paths for your datasets
train_dir = '../DataSet/train'
test_dir = '../DataSet/test'

# Define constants
IMG_HEIGHT, IMG_WIDTH = 224, 224
BATCH_SIZE = 32


# Helper function to extract labels from filenames
def extract_labels_from_filename(filename):
    # Split filename based on '_', ignoring the race and date&time parts
    try:
        parts = filename.split('_')
        age = int(parts[0])  # First part is age
        gender = int(parts[1])  # Second part is gender (0: male, 1: female)
        return age, gender
    except (IndexError, ValueError) as e:
        # Log and handle unexpected filenames
        print(f"Error extracting labels from filename: {filename} - {e}")
        return None, None


# Data preparation functions
def load_and_preprocess_image(filepath, target_size=(IMG_HEIGHT, IMG_WIDTH)):
    img = tf.io.read_file(filepath)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, target_size)
    img = img / 255.0  # Normalize pixel values to [0, 1]
    return img


def create_dataset(filepaths, age_labels, gender_labels, batch_size=32, shuffle=False):
    def process_path(filepath, age, gender):
        img = load_and_preprocess_image(filepath)
        return img, (age, gender)  # Return both age and gender as labels

    filepaths_ds = tf.data.Dataset.from_tensor_slices((filepaths, age_labels, gender_labels))
    dataset = filepaths_ds.map(process_path, num_parallel_calls=tf.data.AUTOTUNE)

    if shuffle:
        dataset = dataset.shuffle(buffer_size=len(filepaths))
    dataset = dataset.batch(batch_size)

    return dataset.prefetch(buffer_size=tf.data.AUTOTUNE)


# Gather filepaths and labels for training set
train_filepaths = []
train_age_labels = []
train_gender_labels = []

for fname in os.listdir(train_dir):
    filepath = os.path.join(train_dir, fname)
    age, gender = extract_labels_from_filename(fname)

    # Only add valid files
    if age is not None and gender is not None:
        train_filepaths.append(filepath)
        train_age_labels.append(age)
        train_gender_labels.append(gender)

# Repeat similar process for the test dataset
test_filepaths = []
test_age_labels = []
test_gender_labels = []

for fname in os.listdir(test_dir):
    filepath = os.path.join(test_dir, fname)
    age, gender = extract_labels_from_filename(fname)

    if age is not None and gender is not None:
        test_filepaths.append(filepath)
        test_age_labels.append(age)
        test_gender_labels.append(gender)

# Prepare datasets
train_dataset = create_dataset(train_filepaths, train_age_labels, train_gender_labels, batch_size=BATCH_SIZE, shuffle=False)
test_dataset = create_dataset(test_filepaths, test_age_labels, test_gender_labels, batch_size=BATCH_SIZE, shuffle=False)

# Build the ResNet50 model with transfer learning
base_model = ResNet50(weights='imagenet', include_top=False, input_shape=(IMG_HEIGHT, IMG_WIDTH, 3))

# Freeze the base model layers
for layer in base_model.layers:
    layer.trainable = False

x = base_model.output
x = GlobalAveragePooling2D()(x)

# Output layers: one for age (regression) and one for gender (binary classification)
age_output = Dense(1, activation='linear', name='age_output')(x)  # Age prediction
gender_output = Dense(1, activation='sigmoid', name='gender_output')(x)  # Gender prediction (0 or 1)

model = Model(inputs=base_model.input, outputs=[age_output, gender_output])

# Compile the model with different losses for age and gender
model.compile(optimizer=Adam(learning_rate=0.0001),  # Lower learning rate for transfer learning
              loss={'age_output': 'mean_squared_error', 'gender_output': 'binary_crossentropy'},
              metrics={'age_output': 'mae', 'gender_output': 'accuracy'})

# Train the model
history = model.fit(train_dataset, epochs=20, validation_data=test_dataset)

# Save the model
model.save('ResNet50.keras')

print("Model training completed and saved.")