"""Contains a variant of the densenet model definition."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

slim = tf.contrib.slim


def trunc_normal(stddev): return tf.truncated_normal_initializer(stddev=stddev)


def bn_act_conv_drp(current, num_outputs, kernel_size, scope='block'):
    current = slim.batch_norm(current, scope=scope + '_bn')
    current = tf.nn.relu(current)
    current = slim.conv2d(current, num_outputs,
                          kernel_size, scope=scope + '_conv')
    current = slim.dropout(current, scope=scope + '_dropout')
    return current


def block(net, layers, growth, scope='block'):
    for idx in range(layers):
        bottleneck = bn_act_conv_drp(net, 4 * growth, [1, 1],
                                     scope=scope + '_conv1x1_' + str(idx))
        tmp = bn_act_conv_drp(bottleneck, growth, [3, 3],
                              scope=scope + '_conv3x3_' + str(idx))
        net = tf.concat(axis=3, values=[net, tmp])
    return net


def transition(net, num_outputs, scope='transition'):
    net = bn_act_conv_drp(net, num_outputs, [1, 1], scope=scope + '_conv1x1')
    net = slim.avg_pool2d(net, [2, 2], stride=2, scope=scope + '_avgpool')
    #net = slim.batch_norm(net, scope=scope + '_bn')
    #net = slim.conv2d(net, num_outputs, [1, 1], scope=scope + '_conv')
    #net = slim.avg_pool2d(net, [2, 2], stride=2, scope=scope + '_avgpool')
    return net


def densenet(images, num_classes=1001, is_training=False,
             dropout_keep_prob=0.8,
             scope='densenet'):
    """Creates a variant of the densenet model.

      images: A batch of `Tensors` of size [batch_size, height, width, channels].
      num_classes: the number of classes in the dataset.
      is_training: specifies whether or not we're currently training the model.
        This variable will determine the behaviour of the dropout layer.
      dropout_keep_prob: the percentage of activation values that are retained.
      prediction_fn: a function to get predictions out of logits.
      scope: Optional variable_scope.

    Returns:
      logits: the pre-softmax activations, a tensor of size
        [batch_size, `num_classes`]
      end_points: a dictionary from components of the network to the corresponding
        activation.
    """
    print('densenet build start')
    growth = 32
    compression_rate = 0.5

    def reduce_dim(input_feature):
        return int(int(input_feature.shape[-1]) * compression_rate)

    end_points = {}

    with tf.variable_scope(scope, 'DenseNet', [images, num_classes]):
        with slim.arg_scope(bn_drp_scope(is_training=is_training,
                                         keep_prob=dropout_keep_prob)) as ssc:
            ##########################
            # Put your code here.
            # 224 x 224,输如图片的尺寸.经过卷积池化后降低
            end_point = 'Conv2d_0'
            net = slim.conv2d(images, 2 * growth, 7, stride=2, scope=end_point)
            end_points[end_point] = net
            end_point = 'MaxPool_0'
            net = slim.max_pool2d(
                net, 3, stride=2, padding='SAME', scope=end_point)
            end_points[end_point] = net

            # 56 x 56,Block1
            end_point = 'Block1'
            net = block(net, 6, growth, scope=end_point)
            end_points[end_point] = net
            end_point = 'Transition1'
            net = transition(net, reduce_dim(net), scope=end_point)
            end_points[end_point] = net

            # 28 x 28, Block2
            end_point = 'Block2'
            net = block(net, 12, growth, scope=end_point)
            end_points[end_point] = net
            end_point = 'Transition2'
            net = transition(net, reduce_dim(net), scope=end_point)
            end_points[end_point] = net

            # block3
            end_point = 'Block3'
            net = block(net, 24, growth, scope=end_point)
            end_points[end_point] = net
            end_point = 'Transition3'
            net = transition(net, reduce_dim(net), scope=end_point)
            end_points[end_point] = net

            # block4
            end_point = 'Block4'
            net = block(net, 16, growth, scope=end_point)
            end_points[end_point] = net

            net = slim.batch_norm(net, scope='last_batch_norm_relu')
            net = tf.nn.relu(net)

            #
            # Global average pooling.
            net = tf.reduce_mean(net, [1, 2], name='pool2', keep_dims=True)

            biases_initializer = tf.constant_initializer(0.1)
            logits = slim.conv2d(net, num_classes, [
                1, 1], biases_initializer=biases_initializer, scope='logits')

            logits = tf.squeeze(logits, [1, 2], name='SpatialSqueeze')

            end_points['Logits'] = logits
            end_points['predictions'] = slim.softmax(
                logits, scope='predictions')

            '''
            # 第一层 block
            net1 = slim.batch_norm(images, scope='block_bn_1')
            net1 = slim.conv2d(net1, 4 * growth, [3, 3], scope='black_conv_3x3_1')
            net1 = tf.nn.relu(net1)

            # 压缩参数
            translation_layer1 = slim.batch_norm(net1, scope='tran_bn_1')
            translation_layer1 = slim.conv2d(
                translation_layer1, 4 * growth, [1, 1], scope='tran_conv_1x1_1')
            translation_layer1 = slim.max_pool2d(
                translation_layer1, [2, 2], scope='tran_pool_1')
            # bottleneck layer
            bottleneck_layer1 = slim.
            '''
            ##########################
    return logits, end_points


def bn_drp_scope(is_training=True, keep_prob=0.8):
    keep_prob = keep_prob if is_training else 1
    with slim.arg_scope(
        [slim.batch_norm],
            scale=True, is_training=is_training, updates_collections=None):
        with slim.arg_scope(
            [slim.dropout],
                is_training=is_training, keep_prob=keep_prob) as bsc:
            return bsc


def densenet_arg_scope(weight_decay=0.004):
    """Defines the default densenet argument scope.

    Args:
      weight_decay: The weight decay to use for regularizing the model.

    Returns:
      An `arg_scope` to use for the inception v3 model.
    """
    with slim.arg_scope(
        [slim.conv2d],
        weights_initializer=tf.contrib.layers.variance_scaling_initializer(
            factor=2.0, mode='FAN_IN', uniform=False),
        activation_fn=None, biases_initializer=None, padding='same',
            stride=1) as sc:
        return sc


densenet.default_image_size = 224
