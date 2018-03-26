import warnings
warnings.filterwarnings("ignore")

import tensorflow as tf
import util
import numpy as np


class DenseConvDense(object):

    VALID_ACTIVATION_FUNCTIONS = {'sigmoid': tf.nn.sigmoid, 'tanh': tf.nn.tanh, 'relu': tf.nn.relu}

    VALID_OPTIMIZERS = {'sgd': tf.train.GradientDescentOptimizer, 'ftrl': tf.train.FtrlOptimizer,
                        'adam': tf.train.AdamOptimizer, 'adadelta': tf.train.AdadeltaOptimizer}

    VALID_COST_FUNCTIONS = ('softmax_cross_entroy')

    def __init__(self, n_input_features, n_outputs, abstraction_activation_functions=('sigmoid', 'tanh', 'relu'),
                 n_hidden_layers=3, n_hidden_nodes=10, keep_probability=0.5, initialization='RBM',
                 optimizer_algorithms=('sgd', 'sgd', 'sgd'), cost_function='softmax_cross_entropy', add_summaries=True,
                 batch_normalization=False):

        assert isinstance(n_hidden_nodes, int) and isinstance(abstraction_activation_functions, tuple)

        assert 0. < keep_probability <= 1.

        assert n_hidden_nodes > 0 and n_hidden_layers > 0

        assert len(optimizer_algorithms) == len(abstraction_activation_functions)

        self.n_input_features = n_input_features

        self.abstraction_activation_functions = abstraction_activation_functions

        self.n_hidden_nodes = n_hidden_nodes

        self.n_hidden_layers = n_hidden_layers

        self.keep_probability = keep_probability

        self.n_outputs = n_outputs

        self.optimizer_algorithms = optimizer_algorithms

        self.cost_function = cost_function

        self.lr = tf.placeholder(tf.float32, name='learning_rate')

        self.add_summaries = add_summaries

        self.batch_normalization = batch_normalization

        self.summaries_dir = '../log'

        #
        # TODO It is not used, yet!
        #
        self.initialization = initialization

        self.model_name = 'M0003'

        #
        # Placeholders
        #
        self.raw_input = None

        self.expected_output = None

        self.keep_prob = tf.placeholder(tf.float32, name='dropout_keep_probability')
        #
        #
        #
        self.saver = None
        #
        #
        #
        self.models = [None for _ in range(len(abstraction_activation_functions))]

        self.cost_functions = [None for _ in range(len(abstraction_activation_functions))]

        self.optimizers = [None for _ in range(len(abstraction_activation_functions))]

        self.correct_predictions = [None for _ in range(len(abstraction_activation_functions))]

        self.accuracies = [None for _ in range(len(abstraction_activation_functions))]

        self.abstract_representation = [[None for _ in range(n_hidden_layers)]
                                        for _ in range(len(abstraction_activation_functions))]

        self.train_writer, self.test_writer = None, None

    def optimize(self, x, y, x_test=None, y_test=None, learning_rate=1e-5, steps=1000, batch_size=1000, shuffle=True):

        assert steps > 0

        assert 0 < batch_size <= x.shape[0]

        self.build_optimizers()

        print('Optimizing model')

        if batch_size is None:
            batch_size = x.shape[0]

        if x_test is None:
            x_test = x

        if y_test is None:
            y_test = y

        with tf.Session() as sess:

            sess.run(tf.global_variables_initializer())
            sess.run(tf.local_variables_initializer())

            test_writer = tf.summary.FileWriter(self.summaries_dir + '/{}'.format(self.model_name))

            n_rows = x.shape[0]

            index = np.array(list(range(n_rows)), dtype=np.int)

            j = 0

            for step in range(steps):

                current_block = 0

                while (current_block < n_rows):

                    if shuffle:
                        np.random.shuffle(index)

                    batch = list(range(current_block, (min(current_block + batch_size, n_rows))))

                    train_results = sess.run([self.merged] + self.optimizers,
                                            feed_dict={self.raw_input: x[index[batch], :],
                                                       self.expected_output: y[index[batch], :],
                                                       self.keep_prob: self.keep_probability,
                                                       self.lr: learning_rate})

                    current_block += batch_size

                    j += 1

                test_results = sess.run([self.merged] + self.accuracies + self.confusion_update,
                                        feed_dict={self.raw_input: x_test, self.expected_output: y_test, self.keep_prob: 1.})

                self.saver.save(sess, '../output/{0}/{0}'.format(self.model_name), global_step=step)

                if self.add_summaries:
                    test_writer.add_summary(test_results[0], step)


    def predict(self, x):

        with tf.Session() as sess:

            sess.run(self.abstraction_activation_functions, feed_dict={})

    def load(self, model_path):
        pass

    def build(self):

        print('Building model')

        self.raw_input = tf.placeholder(tf.float32, shape=(None, self.n_input_features), name='raw_input')

        self.expected_output = tf.placeholder(tf.float32, shape=(None, self.n_outputs), name='expected_output')

        vars_to_save = []

        with tf.name_scope('abstraction_layer'):

            for i, activation_function in enumerate(self.abstraction_activation_functions):

                with tf.name_scope('{}_model'.format(activation_function)):

                    previous_layer_size, previous_layer = self.n_input_features, self.raw_input

                    for j in range(self.n_hidden_layers):

                        layer_name = 'hidden_{}_layer_{}'.format(activation_function, j + 1)

                        with tf.name_scope(layer_name):
                            #
                            # TODO refactor code to define a function to create dense layers
                            #
                            af = self.VALID_ACTIVATION_FUNCTIONS[activation_function]

                            weight_name = 'weight_{}_h{}{}'.format(activation_function, i + 1, j + 1)

                            w = tf.Variable(tf.truncated_normal([previous_layer_size, self.n_hidden_nodes], stddev=.1), name=weight_name)

                            bias_name = 'bias_{}_h{}{}'.format(activation_function, i + 1, j + 1)

                            b = tf.Variable(tf.truncated_normal([self.n_hidden_nodes], stddev=.1), name=bias_name)

                            vars_to_save += [w, b]

                            self.abstract_representation[i][j] = \
                                tf.nn.dropout(af(tf.add(tf.matmul(previous_layer, w), b)), self.keep_prob)

                            if self.batch_normalization:
                                bn_name = 'bn_{}_h{}{}'.format(activation_function, i + 1, j + 1)
                                self.abstract_representation[i][j] = tf.layers.batch_normalization(self.abstract_representation[i][j], name=bn_name)

                            previous_layer, previous_layer_size = self.abstract_representation[i][j], self.n_hidden_nodes

                            if self.add_summaries:
                                util.create_tf_scalar_summaries(w, 'weights')
                                util.create_tf_scalar_summaries(b, 'biases')
                                util.create_tf_scalar_summaries(self.abstract_representation[i][j], 'activation')

                    with tf.name_scope('output_{}_layer'.format(activation_function)):

                        weight_name = 'weight_{}_out'.format(activation_function)

                        w = tf.Variable(tf.truncated_normal([previous_layer_size, self.n_outputs], stddev=.1), name=weight_name)

                        bias_name = 'bias_{}_out'.format(activation_function)

                        b = tf.Variable(tf.truncated_normal([self.n_outputs], stddev=.1), name=bias_name)

                        vars_to_save += [w, b]

                        self.models[i] = tf.add(tf.matmul(previous_layer, w), b)

                        if self.add_summaries:
                            util.create_tf_scalar_summaries(w, 'weights')
                            util.create_tf_scalar_summaries(b, 'biases')
                            util.create_tf_scalar_summaries(self.models[i], 'output')

        self.saver = tf.train.Saver(vars_to_save)

    def build_optimizers(self):

        print('Building optimizers')

        self.confusion_update = []

        for i, (model, optimizer, activation_function) in \
                enumerate(zip(self.models, self.optimizer_algorithms, self.abstraction_activation_functions)):

            if self.cost_function == 'softmax_cross_entropy':

                with tf.name_scope('optimization_{}'.format(activation_function)):

                    self.cost_functions[i] = tf.nn.softmax_cross_entropy_with_logits(labels=self.expected_output, logits=model)

                    self.optimizers[i] = self.VALID_OPTIMIZERS[optimizer](self.lr).minimize(self.cost_functions[i])

                    if self.add_summaries:
                        tf.summary.scalar('cross_entropy_{}'.format(activation_function), tf.reduce_mean(self.cost_functions[i]))

            else:
                raise ValueError('Only softmax_cross_entropy cost function is supported, yet.')

            #
            # TODO Add new performance metrics
            #
            with tf.name_scope('evaluation_{}'.format(activation_function)):

                with tf.name_scope('correct_prediction_{}'.format(activation_function)):
                    self.correct_predictions[i] = tf.equal(tf.argmax(model, 1), tf.argmax(self.expected_output, 1))

                with tf.name_scope('accuracy_{}'.format(activation_function)):
                    self.accuracies[i] = tf.reduce_mean(tf.cast(self.correct_predictions[i], tf.float32))

            if self.add_summaries:

                tf.summary.scalar('accuracy_{}'.format(activation_function), self.accuracies[i])

                #
                # Compute confusion matrix
                #
                with tf.name_scope('confusion_matrix_{}'.format(activation_function)):

                    batch_confusion = tf.confusion_matrix(tf.argmax(self.expected_output, 1), tf.argmax(model, 1),
                                                          num_classes=self.n_outputs,
                                                          name='batch_confusion')

                    confusion = tf.Variable(tf.zeros([self.n_outputs, self.n_outputs],
                                                     dtype=tf.int32),
                                            name='confusion_var_{}'.format(activation_function))

                    self.confusion_update += [confusion.assign(batch_confusion)]

                    confusion_image = tf.reshape(tf.cast(confusion, tf.float32),
                                                 [1, self.n_outputs, self.n_outputs, 1])

                    tf.summary.image('confusion_{}'.format(activation_function), confusion_image)

                #
                # Create summary tensors
                #
                self.merged = tf.summary.merge_all()

